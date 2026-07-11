import type { JobProgress, ManualEntry } from './types';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

export async function createJob(photos: File[]): Promise<string> {
	const form = new FormData();
	for (const photo of photos) {
		form.append('photos', photo);
	}

	const response = await fetch(`${API_BASE}/api/jobs`, {
		method: 'POST',
		body: form
	});

	if (!response.ok) {
		const detail = await response.text();
		throw new Error(detail || 'Upload failed');
	}

	const data: { job_id: string } = await response.json();
	return data.job_id;
}

export async function getJob(jobId: string): Promise<JobProgress> {
	const response = await fetch(`${API_BASE}/api/jobs/${jobId}`);
	if (!response.ok) {
		throw new Error('Failed to fetch job status');
	}
	return response.json();
}

export async function submitManual(jobId: string, entries: ManualEntry[]): Promise<JobProgress> {
	const response = await fetch(`${API_BASE}/api/jobs/${jobId}/manual`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ entries })
	});

	if (!response.ok) {
		throw new Error('Failed to submit manual entries');
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
