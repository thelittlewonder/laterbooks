export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type ProcessingStep = 'idle' | 'ocr' | 'checking' | 'adding' | 'cleanup';

export type BookStatus = 'on_shelf' | 'added' | 'unknown' | 'failed';

export interface UnknownBook {
	title: string;
	photo_index: number;
}

export interface BookResult {
	title: string;
	status: BookStatus;
	message: string | null;
	photo_index: number;
}

export interface JobProgress {
	job_id: string;
	status: JobStatus;
	current_photo: number;
	total_photos: number;
	photos_completed: number;
	current_step: ProcessingStep;
	current_title: string | null;
	books_found: number;
	books_on_shelf: number;
	books_added: number;
	unknown_books: UnknownBook[];
	results: BookResult[];
	error: string | null;
	message: string | null;
}

export interface ManualEntry {
	original_title: string;
	corrected_title: string;
	photo_index: number;
}

export type AppPhase = 'idle' | 'uploading' | 'processing' | 'complete' | 'error';
