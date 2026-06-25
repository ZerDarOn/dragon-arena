import type { Room, ChatMessage, CombatLog } from './types'

export type ServerMessage =
  | { type: 'state_sync'; payload: Room }
  | { type: 'chat'; payload: ChatMessage }
  | { type: 'combat_log'; payload: CombatLog }
  | { type: 'error'; payload: { message: string } }

export type ClientMessage =
  | { type: 'chat'; payload: { channel: string; text: string; target_player?: string } }
  | { type: 'dice_roll'; payload: { expression: string } }
  | { type: 'move'; payload: { token_id: string; path: [number, number][] } }
  | { type: 'modify_value'; payload: { token_id: string; field: string; delta: number } }
  | { type: 'add_state'; payload: { token_id: string; name: string; description: string; ttl: number } }
  | { type: 'place_token'; payload: { token_id: string; x: number; y: number; character?: any } }
  | { type: 'place_unit'; payload: { unit_type: string; name: string; hp: number; armor: number; x: number; y: number; darkvision?: boolean; vision_range?: number; listen_radius?: number; passive_perception?: number; stealth?: number; is_shop?: boolean; shop_items?: string[] } }
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
  | { type: 'buy_item'; payload: { buyer_token_id: string; shop_token_id: string; item_name: string } }

export type ConnectionStatus = 'connecting' | 'open' | 'reconnecting' | 'closed'

const MAX_RECONNECT_DELAY_MS = 10000

export class WSClient {
  private ws: WebSocket | null = null
  private listeners: ((msg: ServerMessage) => void)[] = []
  private statusListeners: ((status: ConnectionStatus) => void)[] = []
  private roomId = ''
  private token = ''
  private closedByUser = false
  private reconnectAttempt = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  // Phase 4: 断线期间待发消息队列
  private outbox: string[] = []
  private static readonly MAX_OUTBOX = 50  // 防止无限堆积

  connect(roomId: string, token: string) {
    this.roomId = roomId
    this.token = token
    this.closedByUser = false
    this.reconnectAttempt = 0
    this._open()
  }

  private _open() {
    this._setStatus(this.reconnectAttempt > 0 ? 'reconnecting' : 'connecting')
    const ws = new WebSocket(
      `ws://${window.location.hostname}:8000/ws/${this.roomId}?token=${encodeURIComponent(this.token)}`,
    )
    this.ws = ws
    ws.onmessage = (ev) => {
      this.listeners.forEach((l) => l(JSON.parse(ev.data)))
    }
    ws.onopen = () => {
      this.reconnectAttempt = 0
      this._setStatus('open')
      // Phase 4: 重连后 flush 待发消息队列
      this._flushOutbox()
    }
    ws.onclose = () => {
      if (this.closedByUser) {
        this._setStatus('closed')
        return
      }
      // 意外断开（服务器重启/网络波动/后端异常）：自动重连，指数退避
      this._setStatus('reconnecting')
      const delay = Math.min(1000 * 2 ** this.reconnectAttempt, MAX_RECONNECT_DELAY_MS)
      this.reconnectAttempt += 1
      this.reconnectTimer = setTimeout(() => this._open(), delay)
    }
    ws.onerror = () => {
      // onclose 会紧跟着触发并处理重连，这里只是让错误不会变成未捕获的控制台异常
    }
  }

  send(msg: ClientMessage) {
    const data = JSON.stringify(msg)
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(data)
    } else {
      // Phase 4: 断线期间入队，重连后自动 flush
      if (this.outbox.length < WSClient.MAX_OUTBOX) {
        this.outbox.push(data)
      }
    }
  }

  private _flushOutbox() {
    if (this.outbox.length === 0) return
    const pending = this.outbox
    this.outbox = []
    for (const data of pending) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(data)
      } else {
        // 又断了，放回队列
        this.outbox.push(data)
        break
      }
    }
  }

  onMessage(l: (msg: ServerMessage) => void) { this.listeners.push(l) }
  onStatus(l: (status: ConnectionStatus) => void) { this.statusListeners.push(l) }
  private _setStatus(s: ConnectionStatus) { this.statusListeners.forEach((l) => l(s)) }

  close() {
    this.closedByUser = true
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null }
    this.outbox = []  // 清空队列
    this.ws?.close()
    this.ws = null
  }
}
