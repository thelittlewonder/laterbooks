<script lang="ts">
	import ProgressBar from '$lib/components/ProgressBar.svelte';
</script>

<div class="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
	<div class="mb-3 flex items-center justify-between text-sm">
		<span class="font-medium text-stone-800">Sending titles to server</span>
		<span class="text-stone-500">Step 3 of 4</span>
	</div>

	<ProgressBar indeterminate />

	<p class="mt-4 text-sm text-stone-600">
		Connecting to Goodreads automation. If Render was idle, this can take up to a minute.
	</p>
</div>
