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

export type InterestItem = {
  topic_id: string;
  slug: string;
  name: string;
  category: string;
  weight: number;
  is_muted: boolean;
  source: string;
};
