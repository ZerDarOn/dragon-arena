declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// @3d-dice/dice-box 没有附带类型声明，这里给一个够用的最小声明
declare module '@3d-dice/dice-box' {
  export interface DiceBoxRollNotation { qty: number; sides: number | string }
  export interface DiceBoxDieResult { groupId: number; rollId: number; sides: number | string; value: number }
  export interface DiceBoxRollGroup { id: number; groupId: number; qty: number; sides: number | string; value: number; rolls: DiceBoxDieResult[] }
  export interface DiceBoxOptions { assetPath: string; [key: string]: any }
  export default class DiceBox {
    constructor(selector: string, options: DiceBoxOptions)
    init(): Promise<void>
    roll(notation: DiceBoxRollNotation[] | string): Promise<DiceBoxRollGroup[]>
    clear(): void
  }
}
