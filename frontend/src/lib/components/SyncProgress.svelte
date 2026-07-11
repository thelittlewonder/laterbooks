<script lang="ts">
	import ProgressBar from '$lib/components/ProgressBar.svelte';

	interface Props {
		message?: string;
	}

	let { message = 'Sending to server for OCR and Goodreads sync. Photos are deleted right after processing.' }: Props =
		$props();
</script>

<div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
	<div class="mb-3 flex items-center justify-between text-sm">
		<span class="font-medium text-stone-800">Preparing sync</span>
	</div>

	<ProgressBar indeterminate />

	<p class="mt-4 text-sm text-stone-600">{message}</p>
</div>
