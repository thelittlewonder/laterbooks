import { createWorker, type Line, type Page, type Worker } from 'tesseract.js';

const NOISE_WORDS = new Set([
	'by',
	'a',
	'an',
	'the',
	'novel',
	'edition',
	'volume',
	'vol',
	'book',
	'new',
	'york',
	'times',
	'bestseller',
	'best',
	'seller',
	'paperback',
	'hardcover',
	'international',
	'award',
	'winner',
	'author',
	'of',
	'and',
	'with',
	'from',
	'penguin',
	'random',
	'house',
	'harper',
	'collins',
	'simon',
	'schuster'
]);

export interface PhotoOcrResult {
	photo_index: number;
	titles: string[];
}

export interface ScanProgress {
	photo_index: number;
	total: number;
	percent: number;
	message: string;
}

export interface ScanUpdate extends ScanProgress {
	completed?: PhotoOcrResult[];
}

let workerPromise: Promise<Worker> | null = null;
let currentProgress: ((percent: number) => void) | undefined;

async function getWorker(): Promise<Worker> {
	if (!workerPromise) {
		workerPromise = createWorker('eng', undefined, {
			logger: (message) => {
				if (message.status === 'recognizing text' && currentProgress) {
					currentProgress(message.progress);
				}
			}
		});
	}
	return workerPromise;
}

export async function terminateOcr(): Promise<void> {
	if (workerPromise) {
		const worker = await workerPromise;
		await worker.terminate();
		workerPromise = null;
	}
}

function cleanLine(text: string): string {
	return text
		.replace(/[|•·]/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

function isLikelyTitle(text: string): boolean {
	if (text.length < 2 || text.length > 80) return false;
	if (!/[a-zA-Z]/.test(text)) return false;
	if (/^\d+$/.test(text)) return false;
	if (/^isbn/i.test(text)) return false;

	const words = text.toLowerCase().split(/\s+/);
	const noiseCount = words.filter((word) => NOISE_WORDS.has(word)).length;
	if (noiseCount / words.length > 0.6) return false;

	return true;
}

function scoreLine(line: Line, imageHeight: number): number {
	const height = line.bbox.y1 - line.bbox.y0;
	const top = line.bbox.y0;
	const width = line.bbox.x1 - line.bbox.x0;
	const text = cleanLine(line.text);
	const wordCount = text.split(/\s+/).length;

	let score = height * 2 + (1 - top / Math.max(imageHeight, 1)) * 50;
	score += Math.min(width / 20, 30);

	if (wordCount >= 1 && wordCount <= 6) score += 20;
	if (wordCount > 8) score -= 30;
	if (text === text.toUpperCase() && wordCount <= 5) score += 10;

	return score;
}

function collectLines(page: Page): Line[] {
	const lines: Line[] = [];
	for (const block of page.blocks ?? []) {
		for (const paragraph of block.paragraphs ?? []) {
			lines.push(...(paragraph.lines ?? []));
		}
	}
	return lines;
}

function pickTitles(lines: Line[]): string[] {
	if (lines.length === 0) return [];

	const imageHeight = Math.max(...lines.map((line) => line.bbox.y1), 1);
	const ranked = lines
		.map((line) => ({
			text: cleanLine(line.text),
			score: scoreLine(line, imageHeight)
		}))
		.filter((entry) => isLikelyTitle(entry.text))
		.sort((a, b) => b.score - a.score);

	const titles: string[] = [];
	const seen = new Set<string>();

	for (const entry of ranked) {
		const key = entry.text.toLowerCase();
		if (seen.has(key)) continue;
		seen.add(key);
		titles.push(entry.text);
		if (titles.length >= 3) break;
	}

	return titles;
}

export async function extractTitlesFromFile(
	file: File,
	photoIndex: number,
	onProgress?: (percent: number) => void
): Promise<PhotoOcrResult> {
	currentProgress = onProgress;
	try {
		const worker = await getWorker();
		const { data } = await worker.recognize(file, {}, { blocks: true });
		const lines = collectLines(data);
		const titles = pickTitles(lines);
		return { photo_index: photoIndex, titles };
	} finally {
		currentProgress = undefined;
	}
}

export async function scanPhotos(
	files: File[],
	onProgress: (progress: ScanUpdate) => void
): Promise<PhotoOcrResult[]> {
	const results: PhotoOcrResult[] = [];

	try {
		onProgress({
			photo_index: 0,
			total: files.length,
			percent: 0,
			message: 'Loading OCR engine…',
			completed: []
		});

		for (let index = 0; index < files.length; index++) {
			onProgress({
				photo_index: index,
				total: files.length,
				percent: 0,
				message: `Reading cover ${index + 1} of ${files.length}`,
				completed: results
			});

			const result = await extractTitlesFromFile(files[index], index, (percent) => {
				onProgress({
					photo_index: index,
					total: files.length,
					percent: Math.round(percent * 100),
					message: `Reading cover ${index + 1} of ${files.length}`,
					completed: results
				});
			});

			results.push(result);
			onProgress({
				photo_index: index,
				total: files.length,
				percent: 100,
				message: `Finished cover ${index + 1} of ${files.length}`,
				completed: results
			});
		}
	} finally {
		await terminateOcr();
	}

	return results;
}
