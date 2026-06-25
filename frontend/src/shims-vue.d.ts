declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// @3d-dice/dice-box-threejs 没有附带类型声明，这里给一个够用的最小声明
declare module '@3d-dice/dice-box-threejs' {
  export interface DiceBoxThreeOptions { [key: string]: any }
  export default class DiceBox {
    constructor(selector: string, options?: DiceBoxThreeOptions)
    initialize(): Promise<void>
    roll(notation: string): Promise<any>
    clearDice(): void
    updateConfig(options: DiceBoxThreeOptions): Promise<void>
  }
}
