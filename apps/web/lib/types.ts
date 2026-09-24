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

export type InterestItem = {
  topic_id: string;
  slug: string;
  name: string;
  category: string;
  weight: number;
  is_muted: boolean;
  source: string;
};
