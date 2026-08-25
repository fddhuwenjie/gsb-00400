import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', component: () => import('../views/Login.vue') },
  { path: '/dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/files', component: () => import('../views/Files.vue') },
  { path: '/documents/:id', component: () => import('../views/DocumentDetail.vue') },
  { path: '/review', component: () => import('../views/Review.vue') },
  { path: '/search', component: () => import('../views/Search.vue') }
]

export default createRouter({ history: createWebHistory(), routes })
