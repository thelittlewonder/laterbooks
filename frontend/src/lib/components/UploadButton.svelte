<script lang="ts">
	interface Props {
		disabled?: boolean;
		loading?: boolean;
		count: number;
		onupload: () => void;
	}

	let { disabled = false, loading = false, count, onupload }: Props = $props();
</script>

<button
	type="button"
	class="w-full rounded-xl bg-stone-900 px-6 py-3 text-sm font-medium text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-40"
	disabled={disabled || loading || count === 0}
	onclick={onupload}
>
	{#if loading}
		Starting…
	{:else}
		Read & sync {count} photo{count === 1 ? '' : 's'}
	{/if}
</button>
