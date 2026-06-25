import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'

/**
 * 统一权限原语（仿 FVTT document ownership / 枭雄分级）。
 *
 * 设计：内容（资源库、角色卡）对所有登录用户**可读**，能不能**改**由权限决定，
 * 而不是"管理员看一套界面、玩家看另一套界面"的二元分叉。
 * 目前权限边界 == 是否管理员；将来要做 per-entry ownership 时只改这里，调用方不动。
 */
export function usePermission() {
  const auth = useAuthStore()
  const isAdmin = computed(() => auth.isAdmin)

  return {
    isAdmin,
    /** 增删改资源库（角色/道具/怪物/装备/物件模板） */
    canManageLibrary: isAdmin,
    /** 从资源库拖拽到地图落子（投放 Token） */
    canSpawnFromLibrary: isAdmin,
    /** 浏览"全员角色卡库"（含他人底牌，敏感） */
    canViewAllSheets: isAdmin,
    /** 编辑某张角色卡：本人或管理员 */
    canEditSheet: (ownerId?: string | null) => auth.isAdmin || ownerId === auth.user?.id,
  }
}
