<script lang="ts">
	import ProgressBar from '$lib/components/ProgressBar.svelte';
</script>

<div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
	<div class="mb-3 flex items-center justify-between text-sm">
		<span class="font-medium text-stone-800">Uploading photos</span>
		<span class="text-stone-500">Step 2 of 4</span>
	</div>

	<ProgressBar indeterminate />

	<p class="mt-4 text-sm text-stone-600">
		Sending to server for OCR and Goodreads sync. Photos are deleted right after processing.
	</p>
</div>
