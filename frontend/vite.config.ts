import tailwindcss from '@tailwindcss/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit(),
		SvelteKitPWA({
			registerType: 'autoUpdate',
			manifest: {
				name: 'shelfie',
				short_name: 'shelfie',
				description: 'Sync book cover photos to your Goodreads Want to Read shelf',
				theme_color: '#1c1917',
				background_color: '#f5f5f4',
				display: 'standalone',
				start_url: '/',
				icons: [
					{
						src: '/icons/icon-192.png',
						sizes: '192x192',
						type: 'image/png'
					},
					{
						src: '/icons/icon-512.png',
						sizes: '512x512',
						type: 'image/png'
					}
				]
			},
			workbox: {
				globPatterns: ['**/*.{js,css,html,ico,png,svg,webp,woff2}']
			},
			devOptions: {
				enabled: true
			}
		})
	],
	server: {
		proxy: {
			'/api': 'http://localhost:8000',
			'/health': 'http://localhost:8000'
		}
	}
});
