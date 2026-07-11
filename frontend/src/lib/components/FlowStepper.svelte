<script lang="ts">
	import type { AppPhase } from '$lib/types';

	interface Step {
		id: string;
		label: string;
	}

	interface Props {
		phase: AppPhase;
	}

	let { phase }: Props = $props();

	const steps: Step[] = [
		{ id: 'select', label: 'Select' },
		{ id: 'read', label: 'Read' },
		{ id: 'sync', label: 'Sync' },
		{ id: 'done', label: 'Done' }
	];

	function activeIndex(current: AppPhase): number {
		switch (current) {
			case 'scanning':
				return 1;
			case 'syncing':
			case 'processing':
				return 2;
			case 'complete':
				return 3;
			case 'error':
				return 2;
			default:
				return 0;
		}
	}

	let current = $derived(activeIndex(phase));

	function stepStatus(index: number): 'complete' | 'active' | 'upcoming' {
		if (index < current) return 'complete';
		if (index === current) return 'active';
		return 'upcoming';
	}
</script>

<nav aria-label="Sync progress" class="rounded-2xl border border-stone-200 bg-white px-4 py-4 shadow-sm">
	<ol class="flex items-center justify-between gap-1">
		{#each steps as step, index (step.id)}
			{@const status = stepStatus(index)}
			<li class="flex min-w-0 flex-1 items-center {index < steps.length - 1 ? 'gap-1' : ''}">
				<div class="flex min-w-0 flex-col items-center gap-1.5">
					<span
						class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors
							{status === 'complete'
							? 'bg-stone-900 text-white'
							: status === 'active'
								? 'bg-stone-900 text-white ring-4 ring-stone-200'
								: 'bg-stone-100 text-stone-400'}"
						aria-current={status === 'active' ? 'step' : undefined}
					>
						{#if status === 'complete'}
							✓
						{:else}
							{index + 1}
						{/if}
					</span>
					<span
						class="truncate text-[10px] font-medium uppercase tracking-wide
							{status === 'active' ? 'text-stone-900' : status === 'complete' ? 'text-stone-600' : 'text-stone-400'}"
					>
						{step.label}
					</span>
				</div>
				{#if index < steps.length - 1}
					<div
						class="mx-1 mt-[-1rem] h-0.5 flex-1 rounded-full {index < current ? 'bg-stone-800' : 'bg-stone-200'}"
						aria-hidden="true"
					></div>
				{/if}
			</li>
		{/each}
	</ol>
</nav>
