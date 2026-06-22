import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import WorkbenchView from '../views/WorkbenchView.vue'
import BattleView from '../views/BattleView.vue'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: LoginView },
  {
    path: '/workbench', name: 'workbench', component: WorkbenchView,
    meta: { requiresAuth: true },
  },
  {
    path: '/battle/:roomId', name: 'battle', component: BattleView, props: true,
    meta: { requiresAuth: true },
  },
  { path: '/', redirect: '/login' },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'workbench' }
  }
})

export default router
