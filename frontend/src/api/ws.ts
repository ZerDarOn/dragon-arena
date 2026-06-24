import type { Room, ChatMessage, CombatLog } from './types'

export type ServerMessage =
  | { type: 'state_sync'; payload: Room }
  | { type: 'chat'; payload: ChatMessage }
  | { type: 'combat_log'; payload: CombatLog }
  | { type: 'error'; payload: { message: string } }

export type ClientMessage =
  | { type: 'chat'; payload: { channel: string; text: string; target_player?: string } }
  | { type: 'dice_roll'; payload: { sides: number; modifier?: number } }
  | { type: 'move'; payload: { token_id: string; path: [number, number][] } }
  | { type: 'modify_value'; payload: { token_id: string; field: string; delta: number } }
  | { type: 'add_state'; payload: { token_id: string; name: string; description: string; ttl: number } }
  | { type: 'place_token'; payload: { token_id: string; x: number; y: number; character?: any } }
  | { type: 'place_unit'; payload: { unit_type: string; name: string; hp: number; armor: number; x: number; y: number; darkvision?: boolean; vision_range?: number; listen_radius?: number; passive_perception?: number; stealth?: number } }
  | { type: 'rotate_token'; payload: { token_id: string; facing: number } }
  | { type: 'size_token'; payload: { token_id: string; size: number } }
  | { type: 'attack'; payload: { attacker_id: string; defender_id: string } }
  | { type: 'defend'; payload: { token_id: string } }
  | { type: 'sprint'; payload: { token_id: string; path: [number, number][] } }
  | { type: 'use_item'; payload: { token_id: string; item_name: string } }
  | { type: 'set_terrain'; payload: { x: number; y: number; type: string } }
  | { type: 'set_cell_meta'; payload: { x: number; y: number; is_dark?: boolean; light_radius?: number } }
  | { type: 'fill_terrain'; payload: { x1: number; y1: number; x2: number; y2: number; type: string } }
  | { type: 'resize_map'; payload: { width: number; height: number } }
  | { type: 'end_turn'; payload: Record<string, never> }
  | { type: 'set_poison_circle'; payload: { center_x: number; center_y: number; radius: number; enabled: boolean } }
  | { type: 'set_fog_of_war'; payload: { enabled: boolean } }
  | { type: 'set_turn_order'; payload: { order: string[] } }
  | { type: 'force_set_actor'; payload: { token_id: string } }
  | { type: 'clear_combat_log'; payload: Record<string, never> }
  | { type: 'shuffle_turn_order'; payload: Record<string, never> }
  | { type: 'start_game'; payload: Record<string, never> }
  | { type: 'spawn_token'; payload: { actor_id: string; x: number; y: number } }

export class WSClient {
  private ws: WebSocket | null = null
  private listeners: ((msg: ServerMessage) => void)[] = []

  connect(roomId: string, token: string) {
    this.ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/${roomId}?token=${encodeURIComponent(token)}`)
    this.ws.onmessage = (ev) => {
      this.listeners.forEach((l) => l(JSON.parse(ev.data)))
    }
  }
  send(msg: ClientMessage) { this.ws?.send(JSON.stringify(msg)) }
  onMessage(l: (msg: ServerMessage) => void) { this.listeners.push(l) }
  close() { this.ws?.close(); this.ws = null }
}
