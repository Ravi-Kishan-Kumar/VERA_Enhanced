export const ASPECTS = ["sound_quality", "bass", "battery_life", "comfort", "fit", "build_quality", "connectivity", "microphone", "noise_cancellation", "value"] as const;
export type AspectKey = typeof ASPECTS[number];
export type Sentiment = "positive" | "negative" | "neutral" | "not_mentioned";
export type Aspect = {
  detected: boolean; sentiment: Sentiment; confidence: number;
  prob_neg?: number | null; prob_neu?: number | null; prob_pos?: number | null;
};
export type AspectSummary = { mention_count: number; detected_fraction: number; positive: number; negative: number; neutral: number; net_sentiment: number; dominant_sentiment: Sentiment };
export type ReviewInput = { text: string; star_rating: number; helpful_votes: number | null; verified_purchase: boolean | null; product_title: string | null; product_asin: string | null; product_category: string };
export type Review = ReviewInput & {
  id: number; status: "pending" | "processing" | "done" | "failed";
  corrected_score: number | null; interval_lower: number | null; interval_upper: number | null;
  confidence_value: number | null; star_text_gap: number | null; review_quality: number | null;
  aspects: Partial<Record<AspectKey, Aspect>> | null; flags: Record<string, unknown> | null;
  explanation: string | null; error_message: string | null; created_at: string; updated_at: string;
};
export type ReviewTask = { review_id: number; task_id: string | null; status: string; message: string };
export type Product = {
  asin: string; title: string | null; product_category?: string; price_inr?: number | null;
  corrected_score: number | null; uncertainty: number | null;
  trust_weighted_score: number | null; star_average: number | null; review_count: number;
  rank_position: number | null; previous_rank_position?: number | null;
  aspect_summary?: Partial<Record<AspectKey, AspectSummary>> | null;
};
export type ProductDetail = Product & { eb_shrinkage_factor: number | null; last_aggregated_at: string | null; reviews: Review[]; reviews_total: number; reviews_limit: number; reviews_offset: number; reviews_has_more: boolean };

export type AnalyticsPerformance = {
  overall_mae: number;
  rating_inflation_index: number;
  conformal_coverage_rate: number;
  total_reviews: number;
  completed_reviews: number;
  pending_reviews: number;
  processing_reviews: number;
  failed_reviews: number;
  total_products: number;
};

export type AnalyticsAspect = {
  aspect: string;
  label: string;
  mention_count: number;
  mention_pct: number;
  positive_pct: number;
  negative_pct: number;
  neutral_pct: number;
  net_sentiment: number;
};

export const aspectName = (key: string) => key.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
export const score = (value: number | null | undefined) => value == null ? "—" : value.toFixed(2);

export type ProductAdvisorItem = {
  asin: string;
  title: string;
  category: "earbuds" | "headphones";
  price_inr: number | null;
  bracket: "budget" | "mid" | "premium";
  corrected_score: number;
  star_average: number;
  uncertainty: number;
  review_count: number;
  aspect_summary: Record<string, { net_sentiment?: number; mention_pct?: number }>;
  top_strengths: string[];
  match_score?: number | null;
  reason?: string | null;
  award?: string;
  award_reason?: string;
};

export type BracketSuggestions = {
  earbuds: {
    budget: ProductAdvisorItem[];
    mid: ProductAdvisorItem[];
    premium: ProductAdvisorItem[];
  };
  headphones: {
    budget: ProductAdvisorItem[];
    mid: ProductAdvisorItem[];
    premium: ProductAdvisorItem[];
  };
  overall_top_3_india: ProductAdvisorItem[];
};

export type AdvisorResponse = {
  total_matches: number;
  recommendations: ProductAdvisorItem[];
  by_bracket: {
    budget: ProductAdvisorItem[];
    mid: ProductAdvisorItem[];
    premium: ProductAdvisorItem[];
  };
};

export type ComparisonStudy = {
  study_title: string;
  sample_sizes: { earbuds: number; headphones: number; total: number };
  overall_calibrated_scores: { earbuds_mean: number; headphones_mean: number; difference: number };
  hypotheses_evaluation: Record<string, {
    hypothesis: string;
    confirmed: boolean;
    finding?: string;
    [key: string]: unknown;
  }>;
  aspect_comparison_matrix: Record<string, {
    aspect: string;
    earbuds_mean_net_sentiment: number;
    headphones_mean_net_sentiment: number;
    delta_headphones_minus_earbuds: number;
    statistically_significant: boolean;
    mann_whitney_p_value: number;
  }>;
};

export type DataAnalysisReport = {
  corpus_summary: {
    total_reviews: number;
    earbuds_reviews: number;
    headphones_reviews: number;
    mean_star_rating: number;
    mean_calibrated_experience_score: number;
    systematic_inflation: number;
    inflation_percentage: string;
  };
  inflation_distribution: Array<{ gap_range: string; percentage: number; count: number }>;
  star_vs_calibrated: Array<{ stars: number; raw_percentage: number; vera_calibrated_percentage: number }>;
  key_findings: string[];
};

export type WebProductItem = {
  name: string;
  brand: string;
  category: "earbuds" | "headphones";
  price_inr: number;
  price_str: string;
  rating: number;
  reviews_count: string;
  price_bracket: "budget" | "mid" | "premium";
  specs: {
    driver: string;
    battery: string;
    anc: string;
    bluetooth: string;
    codecs: string;
    weight: string;
  };
  pros: string[];
  cons: string[];
  match_score?: number;
  match_reason?: string;
  url: string;
  merchant: string;
};

export type WebAdvisorResponse = {
  matches: WebProductItem[];
  budget: WebProductItem[];
  mid: WebProductItem[];
  premium: WebProductItem[];
  top_overall: WebProductItem[];
  total_analyzed: number;
  total_matching: number;
  fallback_applied?: boolean;
  live_market_insights: string;
  applied_filters?: {
    category?: string;
    min_price?: number | null;
    max_price?: number | null;
    price_bracket?: string;
    query_text?: string | null;
  };
  source: string;
};

export type WebCompareResponse = {
  product_a: WebProductItem & {
    scores: Record<string, number>;
    live_snippet?: string;
  };
  product_b: WebProductItem & {
    scores: Record<string, number>;
    live_snippet?: string;
  };
  winners: Record<string, string>;
  verdict: string;
  source: string;
};

export type ChatProduct = {
  name: string;
  brand: string;
  category: "earbuds" | "headphones" | string;
  price_str: string;
  price_inr: number;
  rating: number;
  reviews_count: string;
  specs: Record<string, string>;
  pros: string[];
  cons: string[];
  url: string;
  merchant: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  suggested_products?: ChatProduct[];
  follow_up_questions?: string[];
};

export type ChatResponse = {
  reply: string;
  suggested_products: ChatProduct[];
  follow_up_questions: string[];
};


