import type { Room, ChatMessage, DiceResult } from './types'

export type ServerMessage =
  | { type: 'state_sync'; payload: Room }
  | { type: 'chat'; payload: ChatMessage }
  | { type: 'dice_result'; payload: { actor: string } & DiceResult }
  | { type: 'error'; payload: { message: string } }

export type ClientMessage =
  | { type: 'chat'; payload: { channel: string; text: string; target_player?: string } }
  | { type: 'dice_roll'; payload: { sides: number; modifier?: number } }
  | { type: 'move'; payload: { token_id: string; path: [number, number][] } }
  | { type: 'modify_value'; payload: { token_id: string; field: string; delta: number } }
  | { type: 'add_state'; payload: { token_id: string; name: string; description: string; ttl: number } }
  | { type: 'place_token'; payload: { token_id: string; x: number; y: number } }
  | { type: 'set_terrain'; payload: { x: number; y: number; type: string } }
  | { type: 'end_turn'; payload: Record<string, never> }
  | { type: 'set_turn_order'; payload: { order: string[] } }
  | { type: 'start_game'; payload: Record<string, never> }

export class WSClient {
  private ws: WebSocket | null = null
  private listeners: ((msg: ServerMessage) => void)[] = []

  connect(roomId: string, playerId: string, nickname: string) {
    this.ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/${roomId}?player_id=${playerId}&nickname=${encodeURIComponent(nickname)}`)
    this.ws.onmessage = (ev) => {
      this.listeners.forEach((l) => l(JSON.parse(ev.data)))
    }
  }
  send(msg: ClientMessage) { this.ws?.send(JSON.stringify(msg)) }
  onMessage(l: (msg: ServerMessage) => void) { this.listeners.push(l) }
  close() { this.ws?.close(); this.ws = null }
}
