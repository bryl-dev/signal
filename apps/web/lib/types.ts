export type User = {
  id: string;
  email: string;
  created_at: string;
  onboarded: boolean;
};

export type Topic = {
  id: string;
  slug: string;
  name: string;
  category: string;
  description: string | null;
};

export type TopicCategory = {
  id: string;
  name: string;
  topics: Topic[];
};

export type DocumentItem = {
  id: string;
  title: string;
  url: string;
  source_name: string;
  source_type: string;
  author: string | null;
  published_at: string | null;
  ingested_at: string;
  content_type: string;
  excerpt: string;
};

export type StoryMember = {
  document_id: string;
  title: string;
  url: string;
  source_name: string;
  published_at: string | null;
  method: "seed" | "content_hash" | "embedding";
  similarity: number | null;
};

export type StoryItem = {
  id: string;
  title: string;
  url: string;
  excerpt: string;
  first_seen_at: string;
  last_seen_at: string;
  source_count: number;
  members: StoryMember[];
};

export type IngestResult = {
  sources: number;
  fetched: number;
  upserted: number;
  errors: Array<{ source: string; error: string }>;
  embedded: number;
  stories_created: number;
  joined_content_hash: number;
  joined_embedding: number;
  clustering_error: string | null;
};

export type InterestItem = {
  topic_id: string;
  slug: string;
  name: string;
  category: string;
  weight: number;
  is_muted: boolean;
  source: string;
};
