import type { JobProgress, ManualEntry } from './types';

function apiUrl(path: string): string {
	const base = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

	if (!base) {
		if (import.meta.env.DEV) {
			return path;
		}
		throw new Error(
			'API not configured. In Netlify, set VITE_API_URL to your Render URL and redeploy.'
		);
	}

	return `${base}${path}`;
}

function networkErrorMessage(err: unknown): string {
	const message = err instanceof Error ? err.message : 'Network error';

	if (message === 'Load failed' || message === 'Failed to fetch') {
		return (
			'Could not reach the API. Common causes: ' +
			'(1) Render service is waking up — open your Render URL/health in a tab, wait 60s, retry; ' +
			'(2) CORS — on Render set CORS_ORIGINS to your Netlify URL; ' +
			'(3) wrong VITE_API_URL on Netlify — redeploy after fixing.'
		);
	}

	if (err instanceof DOMException && err.name === 'TimeoutError') {
		return 'Request timed out. Render may still be waking up — wait a minute and try again.';
	}

	return message;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
	try {
		return await fetch(apiUrl(path), {
			...init,
			signal: init?.signal ?? AbortSignal.timeout(120_000)
		});
	} catch (err) {
		throw new Error(networkErrorMessage(err));
	}
}

async function parseError(response: Response): Promise<string> {
	const text = await response.text();
	const trimmed = text.trimStart();

	if (trimmed.startsWith('<!DOCTYPE') || trimmed.startsWith('<html')) {
		return 'API request hit Netlify instead of Render. Set VITE_API_URL to your Render backend URL and redeploy.';
	}

	try {
		const json = JSON.parse(text) as { detail?: string };
		if (json.detail) return json.detail;
	} catch {
		// not JSON
	}

	return text || `Request failed (${response.status})`;
}

export async function createJob(photos: File[]): Promise<string> {
	const form = new FormData();
	for (const photo of photos) {
		form.append('photos', photo);
	}

	const response = await apiFetch('/api/jobs', {
		method: 'POST',
		body: form
	});

	if (!response.ok) {
		throw new Error(await parseError(response));
	}

	const data: { job_id: string } = await response.json();
	return data.job_id;
}

export async function getJob(jobId: string): Promise<JobProgress> {
	const response = await apiFetch(`/api/jobs/${jobId}`);
	if (!response.ok) {
		throw new Error(await parseError(response));
	}
	return response.json();
}

export async function submitManual(jobId: string, entries: ManualEntry[]): Promise<JobProgress> {
	const response = await apiFetch(`/api/jobs/${jobId}/manual`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ entries })
	});

	if (!response.ok) {
		throw new Error(await parseError(response));
	}
	return response.json();
}

export function pollJob(
	jobId: string,
	onUpdate: (progress: JobProgress) => void,
	intervalMs = 1000
): () => void {
	let active = true;

	const tick = async () => {
		while (active) {
			try {
				const progress = await getJob(jobId);
				onUpdate(progress);
				if (progress.status === 'completed' || progress.status === 'failed') {
					break;
				}
			} catch {
				// keep polling on transient errors
			}
			await new Promise((resolve) => setTimeout(resolve, intervalMs));
		}
	};

	void tick();
	return () => {
		active = false;
	};
}
