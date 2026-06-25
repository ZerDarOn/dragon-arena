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
  name: string; avatar_url?: string | null
  gender: string; profession: string; talent: string
  hp_base: number; armor_base: number; ap_base: number
  gold: number; backpack: string[]
  equipment_slots: (string | null)[]; skill_slots: (string | null)[]
  darkvision: boolean; vision_range: number; listen_radius: number
  passive_perception: number; stealth: number
  // present only for owner/admin views; absent for other viewers
  secret_backups?: string[]
  created_at: number; updated_at: number
}

// ---- Map ----
export interface TerrainCell {
  x: number; y: number
  type: 'flat' | 'wall' | 'grass' | 'water' | 'high'
  height: number
  smoke_ttl: number | null
  is_smoke: boolean
  is_dark: boolean
  light_radius: number
}
export interface GameMap {
  width: number; height: number
  terrain: TerrainCell[][]
  safe_zone: { center: { x: number; y: number }; radius: number }
}

export interface RoomConfig {
  map_width: number; map_height: number; vision_range: number
  move_ap_cost: number; sprint_ap_cost: number; sprint_distance: number
  start_hp: number; start_armor: number; start_ap: number; creation_points: number
  dc_melee: number; dc_mid: number; dc_ranged: number
  crit_success: number; crit_fail: number; defend_ap_cost: number
  speak_radius: number; shout_multiplier: number; sound_through_wall: boolean
  turn_time_limit_sec: number; ap_regen: number
  fog_of_war_enabled?: boolean
  poison_circle_enabled?: boolean
  poison_circle_center_x?: number
  poison_circle_center_y?: number
  poison_circle_radius?: number
  poison_circle_damage_base?: number
  poison_circle_damage_per_dist?: number
  poison_circle_shrink_per_turn?: number
  poison_circle_min_radius?: number
}

export interface StateTag { id: string; name: string; description: string; ttl: number; intensity?: number }

export interface Token {
  id: string; type: string; owner_id?: string; actor_id?: string
  position?: { x: number; y: number }; facing: number
  hp: number; max_hp: number; armor: number; ap: number; max_ap: number
  gold: number; score: number; vision_range: number; listen_radius: number
  passive_perception: number; darkvision: boolean; stealth: number
  states: StateTag[]; equipment_slots: (string | null)[]; skill_slots: (string | null)[]
  backpack: string[]; is_dead: boolean; is_hidden: boolean; size: number
  character_name?: string
  avatar_url?: string  // 头像 URL（base64 或外部链接）
  item_charges?: Record<string, number>  // 道具剩余次数
  is_shop?: boolean
  shop_items?: string[]
}

export interface Player {
  id: string; name: string; is_host: boolean; is_connected: boolean
  token_id?: string; nickname: string
}

export interface Room {
  id: string; name: string; config: RoomConfig
  players: Record<string, Player>; tokens: Record<string, Token>
  game_map?: GameMap
  current_actor?: string; turn_order: string[]
  big_turn: number; sub_turn: number
  // 服务端按玩家定制追加（管理员视图无）
  visible_cells?: [number, number][]
  detected_tokens?: Record<string, string>
}

export interface ChatMessage {
  id: string; sender_id: string; channel: string; content_type: string
  text?: string; audio_url?: string; recipients?: string[] | null; timestamp: number
  extra?: Record<string, any>  // spatial: attenuation, distance, is_shout
}

export interface CombatLog {
  action: string
  actor_id: string
  target_id?: string
  results: Array<{
    rule: string
    effects: Array<{
      type: string
      success: boolean
      dice?: { value: number; modifier: number; total: number; crit_success: boolean; crit_fail: boolean }
      hit?: { dc: number; roll: number; bonus: number; total: number; is_hit: boolean; is_crit: boolean; is_fail: boolean }
      damage?: { raw_damage: number; armor: number; real_damage: number }
      hp_after?: number
      ap_after?: number
      armor_after?: number
      state_id?: string
      is_hidden?: boolean
      position?: { x: number; y: number }
      reason?: string
    }>
    passive?: boolean
    global?: boolean
  }>
}

export interface DieRoll { sides: number; value: number; kept: boolean }
export interface DiceGroup {
  count: number; sides: number; keep?: 'h' | 'l' | null; keep_n?: number | null
  sign: number; rolls: DieRoll[]
}
export interface DiceResult {
  expression: string
  groups: DiceGroup[]
  value: number; modifier: number; total: number
  crit_success: boolean; crit_fail: boolean; sides: number
}

// ---- Actor Library ----

export interface Actor {
  id: string
  name: string
  type: 'player' | 'npc' | 'monster'
  avatar_url?: string
  hp: number; max_hp: number; armor: number; ap: number; max_ap: number
  vision_range: number; darkvision: number; listen_radius: number
  passive_perception: number; stealth: number
  equipment_slots: (string | null)[]; skill_slots: (string | null)[]
  backpack: string[]
  is_shop: boolean; shop_items: string[]
  created_at: number; updated_at: number
}

export interface ActorCreate {
  name: string
  type?: 'player' | 'npc' | 'monster'
  avatar_url?: string
  hp?: number; max_hp?: number; armor?: number; ap?: number; max_ap?: number
  vision_range?: number; darkvision?: number; listen_radius?: number
  passive_perception?: number; stealth?: number
  equipment_slots?: (string | null)[]; skill_slots?: (string | null)[]
  backpack?: string[]
  is_shop?: boolean; shop_items?: string[]
}

export interface ActorUpdate {
  name?: string
  type?: 'player' | 'npc' | 'monster'
  avatar_url?: string
  hp?: number; max_hp?: number; armor?: number; ap?: number; max_ap?: number
  vision_range?: number; darkvision?: number; listen_radius?: number
  passive_perception?: number; stealth?: number
  equipment_slots?: (string | null)[]; skill_slots?: (string | null)[]
  backpack?: string[]
  is_shop?: boolean; shop_items?: string[]
}

// ---- Item Library (道具库) ----

export interface Item {
  id: string
  name: string
  category: 'weapon' | 'armor' | 'consumable' | 'skill' | 'misc'
  description: string
  effect_text: string
  icon_url?: string | null
  price: number
  created_at: number; updated_at: number
}

export interface ItemCreate {
  name: string
  category?: Item['category']
  description?: string
  effect_text?: string
  icon_url?: string | null
  price?: number
}

export interface ItemUpdate {
  name?: string
  category?: Item['category']
  description?: string
  effect_text?: string
  icon_url?: string | null
  price?: number
}
