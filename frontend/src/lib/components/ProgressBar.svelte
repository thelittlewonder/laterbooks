<script lang="ts">
	interface Props {
		value?: number;
		indeterminate?: boolean;
		size?: 'sm' | 'md';
	}

	let { value = 0, indeterminate = false, size = 'md' }: Props = $props();

	const height = $derived(size === 'sm' ? 'h-1.5' : 'h-2');
</script>

<div class="{height} overflow-hidden rounded-full bg-stone-100" role="progressbar" aria-valuenow={indeterminate ? undefined : value} aria-valuemin={0} aria-valuemax={100}>
	{#if indeterminate}
		<div class="progress-indeterminate {height} w-1/3 rounded-full bg-stone-800"></div>
	{:else}
		<div
			class="{height} rounded-full bg-stone-800 transition-all duration-300"
			style="width: {Math.min(100, Math.max(0, value))}%"
		></div>
	{/if}
</div>

<style>
	.progress-indeterminate {
		animation: indeterminate 1.4s ease-in-out infinite;
	}

	@keyframes indeterminate {
		0% {
			transform: translateX(-100%);
		}
		100% {
			transform: translateX(400%);
		}
	}
</style>
