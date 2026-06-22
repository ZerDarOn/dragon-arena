// ---- Auth ----
export interface UserPublic {
  id: string; nickname: string; is_admin: boolean
  created_at: number; last_login_at: number
}
export interface LoginResponse {
  token: string; user: UserPublic
}

// ---- Character Sheets ----
export interface CharacterSheet {
  id: string; owner_id: string
  name: string; gender: string; profession: string; talent: string
  hp_base: number; armor_base: number; ap_base: number
  gold: number; backpack: string[]
  equipment_slots: (string | null)[]; skill_slots: (string | null)[]
  // present only for owner/admin views; absent for other viewers
  secret_backups?: string[]
  created_at: number; updated_at: number
}

export interface RoomConfig {
  map_width: number; map_height: number; vision_range: number
  move_ap_cost: number; sprint_ap_cost: number; sprint_distance: number
  start_hp: number; start_armor: number; start_ap: number; creation_points: number
  dc_melee: number; dc_mid: number; dc_ranged: number
  crit_success: number; crit_fail: number; defend_ap_cost: number
  speak_radius: number; shout_multiplier: number; sound_through_wall: boolean
  turn_time_limit_sec: number; ap_regen: number
}

export interface StateTag { id: string; name: string; description: string; ttl: number; intensity?: number }

export interface Token {
  id: string; type: string; owner_id?: string
  position?: { x: number; y: number }; facing: number
  hp: number; max_hp: number; armor: number; ap: number; max_ap: number
  gold: number; score: number; vision_range: number; listen_radius: number
  states: StateTag[]; equipment_slots: (string | null)[]; skill_slots: (string | null)[]
  backpack: string[]; is_dead: boolean; is_hidden: boolean
}

export interface Player {
  id: string; name: string; is_host: boolean; is_connected: boolean
  token_id?: string; nickname: string
}

export interface Room {
  id: string; name: string; config: RoomConfig
  players: Record<string, Player>; tokens: Record<string, Token>
  current_actor?: string; turn_order: string[]
  big_turn: number; sub_turn: number
}

export interface ChatMessage {
  id: string; sender_id: string; channel: string; content_type: string
  text?: string; recipients?: string[] | null; timestamp: number
}

export interface DiceResult {
  value: number; modifier: number; total: number
  crit_success: boolean; crit_fail: boolean; sides: number
}
