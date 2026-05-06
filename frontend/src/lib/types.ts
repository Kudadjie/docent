export type Status = 'queued' | 'reading' | 'done';
export type PaperType = 'paper' | 'book' | 'book_chapter';

export interface QueueEntry {
  id: string;
  title: string;
  authors: string;
  year: number | null;
  doi: string | null;
  type: PaperType;
  added: string;
  status: Status;
  order: number;
  category: string | null;
  deadline: string | null;
  tags: string[];
  notes: string;
  mendeley_id: string | null;
  started: string | null;
  finished: string | null;
}

export interface BannerCounts {
  queued: number;
  reading: number;
  done: number;
}

export interface QueueData {
  entries: QueueEntry[];
  banner: BannerCounts;
  last_updated: string | null;
  database_count: number | null;
}

export type FilterValue = 'all' | Status;
