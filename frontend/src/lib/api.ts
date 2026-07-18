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

const WAKE_MAX_WAIT_MS = 120_000;
const WAKE_RETRY_MS = 3_000;

export type WakeProgress = {
	attempt: number;
	elapsedSec: number;
	message: string;
};

/** Ping /health until Render free tier has finished cold-starting. */
export async function wakeBackend(
	onProgress?: (progress: WakeProgress) => void
): Promise<void> {
	const started = Date.now();
	let attempt = 0;

	while (Date.now() - started < WAKE_MAX_WAIT_MS) {
		attempt += 1;
		const elapsedSec = Math.round((Date.now() - started) / 1000);
		onProgress?.({
			attempt,
			elapsedSec,
			message:
				attempt === 1
					? 'Waking up server…'
					: `Waking up server… (${elapsedSec}s)`
		});

		try {
			const response = await fetch(apiUrl('/health'), {
				signal: AbortSignal.timeout(20_000)
			});
			if (response.ok) {
				return;
			}
		} catch {
			// Render cold start — keep retrying
		}

		await new Promise((resolve) => setTimeout(resolve, WAKE_RETRY_MS));
	}

	throw new Error(
		'Server did not wake up in time (Render free tier can take ~90s). Wait a minute and tap Sync again.'
	);
}

type ApiRequestInit = RequestInit & { noRetry?: boolean };

async function apiFetch(path: string, init?: ApiRequestInit): Promise<Response> {
	const { noRetry, ...fetchInit } = init ?? {};
	try {
		return await fetch(apiUrl(path), {
			...fetchInit,
			signal: fetchInit.signal ?? AbortSignal.timeout(180_000)
		});
	} catch (err) {
		// Likely a Render cold start — wake the server and retry once.
		if (!noRetry) {
			try {
				await wakeBackend();
				return await fetch(apiUrl(path), {
					...fetchInit,
					signal: fetchInit.signal ?? AbortSignal.timeout(180_000)
				});
			} catch {
				// fall through to the friendly error below
			}
		}
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
	const response = await apiFetch(`/api/jobs/${jobId}`, { noRetry: true });
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
