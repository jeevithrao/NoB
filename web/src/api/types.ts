export type TourStatus = 'not_purchased' | 'purchased' | 'in_progress' | 'completed_locked';

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  role: string;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface TourListItem {
  id: string;
  name: string;
  description: string | null;
  city: string;
  cover_image: string | null;
  duration_min: number | null;
  distance_km: string | null;
  price_paise: number;
  is_free: boolean;
  status: TourStatus;
  like_count: number;
}

export interface TourDetail extends TourListItem {
  is_published: boolean;
  stop_count: number;
  purchase_id: string | null;
}

export interface StopWithAudio {
  id: string;
  order_index: number;
  name: string;
  narrative_text: string | null;
  lat: string;
  lng: string;
  trigger_radius_m: number;
  audio_url: string;
}

export interface TourPackage {
  tour_id: string;
  name: string;
  stops: StopWithAudio[];
  signed_url_expires_in: number;
}

export interface PurchaseCreateResponse {
  purchase_id: string;
  status: string;
  gateway_order_id: string | null;
  gateway_config: Record<string, unknown>;
}

export interface TourSession {
  id: string;
  tour_id: string;
  stops_visited: number;
  completed: boolean;
  is_resumable: boolean;
  started_at: string;
  completed_at: string | null;
}

export type SessionEventType = 'arrived' | 'audio_started' | 'audio_finished';

export interface SessionEventIn {
  client_event_id: string;
  stop_id: string;
  event_type: SessionEventType;
  occurred_at: string;
}

export interface CommentOut {
  id: string;
  user_id: string;
  user_name: string | null;
  content: string;
  created_at: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}
