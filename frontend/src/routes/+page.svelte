<script lang="ts">
	import PhotoPicker from '$lib/components/PhotoPicker.svelte';
	import UploadButton from '$lib/components/UploadButton.svelte';
	import LiveProgress from '$lib/components/LiveProgress.svelte';
	import FinalSummary from '$lib/components/FinalSummary.svelte';
	import ManualReview from '$lib/components/ManualReview.svelte';
	import { createJob, pollJob, submitManual } from '$lib/api';
	import type { AppPhase, JobProgress, ManualEntry } from '$lib/types';

	let files = $state<File[]>([]);
	let phase = $state<AppPhase>('idle');
	let jobId = $state<string | null>(null);
	let progress = $state<JobProgress | null>(null);
	let error = $state<string | null>(null);
	let manualSubmitting = $state(false);
	let stopPolling: (() => void) | null = null;

	const isBusy = $derived(
		phase === 'uploading' || phase === 'processing' || manualSubmitting
	);

	function reset() {
		stopPolling?.();
		stopPolling = null;
		files = [];
		jobId = null;
		progress = null;
		error = null;
		phase = 'idle';
		manualSubmitting = false;
	}

	async function handleUpload() {
		if (files.length === 0) return;

		error = null;
		phase = 'uploading';

		try {
			const id = await createJob(files);
			jobId = id;
			phase = 'processing';

			stopPolling = pollJob(id, (update) => {
				progress = update;
				if (update.status === 'completed') {
					phase = 'complete';
				} else if (update.status === 'failed') {
					phase = 'error';
					error = update.error ?? 'Processing failed';
				}
			});
		} catch (err) {
			phase = 'error';
			error = err instanceof Error ? err.message : 'Upload failed';
		}
	}

	async function handleManual(entries: ManualEntry[]) {
		if (!jobId) return;

		manualSubmitting = true;
		phase = 'processing';

		try {
			await submitManual(jobId, entries);
			stopPolling?.();
			stopPolling = pollJob(jobId, (update) => {
				progress = update;
				if (update.status === 'completed') {
					phase = 'complete';
					manualSubmitting = false;
				} else if (update.status === 'failed') {
					phase = 'error';
					error = update.error ?? 'Manual processing failed';
					manualSubmitting = false;
				}
			});
		} catch (err) {
			phase = 'error';
			error = err instanceof Error ? err.message : 'Manual submit failed';
			manualSubmitting = false;
		}
	}
</script>

<svelte:head>
	<title>shelfie</title>
	<meta name="description" content="Sync book cover photos to your Goodreads Want to Read shelf" />
</svelte:head>

<main class="mx-auto min-h-dvh max-w-lg px-4 py-10">
	<header class="mb-8 text-center">
		<h1 class="text-2xl font-semibold tracking-tight text-stone-900">shelfie</h1>
		<p class="mt-2 text-sm text-stone-600">
			Upload book cover photos. Missing titles are added to your Goodreads Want to Read shelf.
		</p>
	</header>

	<div class="space-y-6">
		{#if phase === 'idle' || phase === 'uploading'}
			<PhotoPicker {files} disabled={isBusy} onchange={(selected) => (files = selected)} />
			<UploadButton
				count={files.length}
				disabled={isBusy}
				loading={phase === 'uploading'}
				onupload={handleUpload}
			/>
		{/if}

		{#if phase === 'processing' && progress}
			<LiveProgress {progress} />
		{/if}

		{#if phase === 'complete' && progress}
			<FinalSummary {progress} onreset={reset} />
			{#if progress.unknown_books.length > 0}
				<ManualReview
					books={progress.unknown_books}
					submitting={manualSubmitting}
					onsubmit={handleManual}
				/>
			{/if}
		{/if}

		{#if phase === 'error'}
			<div class="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-800">
				<p class="font-medium">Something went wrong</p>
				<p class="mt-1">{error}</p>
				<button
					type="button"
					class="mt-4 rounded-lg bg-red-900 px-4 py-2 text-xs font-medium text-white"
					onclick={reset}
				>
					Try again
				</button>
			</div>
		{/if}
	</div>
</main>
