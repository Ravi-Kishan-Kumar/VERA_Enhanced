export const ASPECTS = ["sound_quality", "bass", "battery_life", "comfort", "fit", "build_quality", "connectivity", "microphone", "noise_cancellation", "value"] as const;
export type AspectKey = typeof ASPECTS[number];
export type Sentiment = "positive" | "negative" | "neutral" | "not_mentioned";
export type Aspect = { detected: boolean; sentiment: Sentiment; confidence: number };
export type AspectSummary = { mention_count: number; detected_fraction: number; positive: number; negative: number; neutral: number; net_sentiment: number; dominant_sentiment: Sentiment };
export type ReviewInput = { text: string; star_rating: number; helpful_votes: number | null; verified_purchase: boolean | null; product_title: string | null; product_asin: string | null };
export type Review = ReviewInput & {
  id: number; status: "pending" | "processing" | "done" | "failed";
  corrected_score: number | null; interval_lower: number | null; interval_upper: number | null;
  confidence_value: number | null; star_text_gap: number | null; review_quality: number | null;
  aspects: Partial<Record<AspectKey, Aspect>> | null; flags: Record<string, unknown> | null;
  explanation: string | null; error_message: string | null; created_at: string; updated_at: string;
};
export type ReviewTask = { review_id: number; task_id: string | null; status: string; message: string };
export type Product = {
  asin: string; title: string | null; corrected_score: number | null; uncertainty: number | null;
  trust_weighted_score: number | null; star_average: number | null; review_count: number;
  rank_position: number | null; previous_rank_position?: number | null;
  aspect_summary?: Partial<Record<AspectKey, AspectSummary>> | null;
};
export type ProductDetail = Product & { eb_shrinkage_factor: number | null; last_aggregated_at: string | null; reviews: Review[]; reviews_total: number; reviews_limit: number; reviews_offset: number; reviews_has_more: boolean };
export const aspectName = (key: string) => key.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
export const score = (value: number | null | undefined) => value == null ? "—" : value.toFixed(2);
