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
	'schuster',
	'modern',
	'classics',
	'classic',
	'penguin'
]);

/**
 * Crop the photo (not the cover layout) to the main book in frame.
 * Titles can sit anywhere on a cover — we only use size to pick text.
 */
const CROP_WIDTH_RATIO = 0.72;
const CROP_HEIGHT_RATIO = 0.78;
const MAX_OCR_DIMENSION = 1600;
const MIN_HEIGHT_RATIO = 0.4;

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
		.replace(/[|•·*_]+/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

function letterCount(text: string): number {
	return (text.match(/[a-zA-ZÀ-ÿ]/g) || []).length;
}

function isGarbageTitle(text: string): boolean {
	if (letterCount(text) < 5) return true;

	const nonSpace = text.replace(/\s/g, '');
	const letters = letterCount(nonSpace);
	if (letters / nonSpace.length < 0.55) return true;

	const words = text.split(/\s+/).filter(Boolean);
	if (words.length === 1 && words[0].length <= 3) return true;
	if (words.every((word) => word.length <= 2)) return true;

	const weird = (text.match(/[^a-zA-ZÀ-ÿ0-9\s'-]/g) || []).length;
	if (weird / nonSpace.length > 0.25) return true;

	return false;
}

function isLikelyTitle(text: string): boolean {
	if (text.length < 3 || text.length > 120) return false;
	if (!/[a-zA-ZÀ-ÿ]/.test(text)) return false;
	if (/^\d+$/.test(text)) return false;
	if (/^isbn/i.test(text)) return false;
	if (isGarbageTitle(text)) return false;

	const words = text.toLowerCase().split(/\s+/);
	const noiseCount = words.filter((word) => NOISE_WORDS.has(word)).length;
	if (words.length > 0 && noiseCount / words.length > 0.6) return false;

	return true;
}

interface TextLine {
	text: string;
	y0: number;
	y1: number;
	height: number;
	width: number;
	area: number;
}

function toTextLine(line: Line): TextLine {
	const width = line.bbox.x1 - line.bbox.x0;
	const height = line.bbox.y1 - line.bbox.y0;

	return {
		text: cleanLine(line.text),
		y0: line.bbox.y0,
		y1: line.bbox.y1,
		height,
		width,
		area: width * height
	};
}

function groupLines(lines: TextLine[], gap = 28): TextLine[][] {
	const sorted = [...lines].sort((a, b) => a.y0 - b.y0 || a.text.localeCompare(b.text));
	const groups: TextLine[][] = [];

	for (const line of sorted) {
		const last = groups.at(-1);
		if (!last || line.y0 - last.at(-1)!.y1 > gap) {
			groups.push([line]);
		} else {
			last.push(line);
		}
	}

	return groups;
}

function mergeGroup(group: TextLine[]): string {
	return group
		.map((line) => line.text)
		.filter(Boolean)
		.join(' ');
}

/** Drop tiny text (spines, imprints) — keep the largest type on the cover. */
function prominentLines(lines: TextLine[]): TextLine[] {
	if (lines.length === 0) return lines;

	const maxHeight = Math.max(...lines.map((line) => line.height));
	return lines.filter((line) => line.height / maxHeight >= MIN_HEIGHT_RATIO);
}

function scoreTitleGroup(group: TextLine[], text: string): number {
	const totalArea = group.reduce((sum, line) => sum + line.area, 0);
	const avgHeight = group.reduce((sum, line) => sum + line.height, 0) / group.length;
	const maxLineHeight = Math.max(...group.map((line) => line.height));
	const wordCount = text.split(/\s+/).length;

	let score = totalArea * 3 + avgHeight * 14 + maxLineHeight * 6;
	score += Math.min(text.length, 60);

	if (wordCount >= 2 && wordCount <= 12) score += 25;
	if (text === text.toUpperCase()) score += 8;

	return score;
}

function pickTitles(lines: Line[]): string[] {
	if (lines.length === 0) return [];

	const textLines = lines.map(toTextLine).filter((line) => line.text.length > 0);
	if (textLines.length === 0) return [];

	const candidates = prominentLines(textLines);
	const scoped = candidates.length > 0 ? candidates : textLines;

	const groups = groupLines(scoped);
	const ranked = groups
		.map((group) => {
			const text = mergeGroup(group);
			return { text, score: scoreTitleGroup(group, text) };
		})
		.filter((entry) => isLikelyTitle(entry.text))
		.sort((a, b) => b.score - a.score);

	if (ranked.length === 0) return [];

	return [ranked[0].text];
}

async function focusCropImage(file: File): Promise<HTMLCanvasElement> {
	const bitmap = await createImageBitmap(file);
	const sourceWidth = bitmap.width;
	const sourceHeight = bitmap.height;

	const cropWidth = sourceWidth * CROP_WIDTH_RATIO;
	const cropHeight = sourceHeight * CROP_HEIGHT_RATIO;
	const sourceX = (sourceWidth - cropWidth) / 2;
	const sourceY = (sourceHeight - cropHeight) / 2;

	const scale = Math.min(1, MAX_OCR_DIMENSION / Math.max(cropWidth, cropHeight));
	const canvas = document.createElement('canvas');
	canvas.width = Math.round(cropWidth * scale);
	canvas.height = Math.round(cropHeight * scale);

	const ctx = canvas.getContext('2d');
	if (!ctx) {
		bitmap.close();
		throw new Error('Could not prepare image for OCR');
	}

	ctx.drawImage(
		bitmap,
		sourceX,
		sourceY,
		cropWidth,
		cropHeight,
		0,
		0,
		canvas.width,
		canvas.height
	);
	bitmap.close();

	return canvas;
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

export async function extractTitlesFromFile(
	file: File,
	photoIndex: number,
	onProgress?: (percent: number) => void
): Promise<PhotoOcrResult> {
	currentProgress = onProgress;
	try {
		const worker = await getWorker();
		const focused = await focusCropImage(file);
		const { data } = await worker.recognize(focused, {}, { blocks: true });
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
