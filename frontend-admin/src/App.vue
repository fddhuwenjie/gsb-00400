<template>
  <div class="app">
    <!-- 移动端汉堡菜单 -->
    <button v-if="showSidebar" class="hamburger" @click="toggleMenu">☰</button>
    <!-- 移动端遮罩 -->
    <div v-if="mobileMenuOpen" class="overlay" @click="closeMenu"></div>
    <aside v-if="showSidebar" class="sidebar" :class="{ open: mobileMenuOpen }">
      <div class="logo">
        <svg width="32" height="32" viewBox="0 0 48 48" fill="none">
          <rect width="48" height="48" rx="12" fill="#6366f1"/>
          <path d="M24 14L14 20V28L24 34L34 28V20L24 14Z" stroke="white" stroke-width="2"/>
        </svg>
        <span class="logo-text">知识库</span>
      </div>
      <nav>
        <router-link to="/dashboard" @click="closeMenu"><span class="nav-icon">📊</span><span class="nav-label">数据总览</span></router-link>
        <router-link to="/files" @click="closeMenu"><span class="nav-icon">📁</span><span class="nav-label">文件管理</span></router-link>
        <router-link to="/versions" @click="closeMenu"><span class="nav-icon">🗂️</span><span class="nav-label">版本管理</span></router-link>
        <router-link to="/review" @click="closeMenu"><span class="nav-icon">✅</span><span class="nav-label">审核确认</span></router-link>
        <router-link to="/search" @click="closeMenu"><span class="nav-icon">🔍</span><span class="nav-label">知识检索</span></router-link>
      </nav>
      <button class="logout" @click="logout"><span class="nav-label">退出登录</span></button>
    </aside>
    <main :class="{ 'with-sidebar': showSidebar, 'full-page': !showSidebar }">
      <router-view />
    </main>
    <Toast />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { provideToast } from './composables/useToast'
import Toast from './components/Toast.vue'
const route = useRoute()
const router = useRouter()
const showSidebar = computed(() => route.path !== '/login')
const mobileMenuOpen = ref(false)
const toast = provideToast()
const logout = () => { localStorage.removeItem('token'); router.push('/login') }
const toggleMenu = () => { mobileMenuOpen.value = !mobileMenuOpen.value }
const closeMenu = () => { mobileMenuOpen.value = false }
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; }
.app { display: flex; min-height: 100vh; }
.hamburger {
  display: none; position: fixed; top: 16px; left: 16px; z-index: 1001;
  background: white; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 8px 12px; font-size: 20px; cursor: pointer;
}
.overlay {
  display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 999;
}
.sidebar {
  width: 240px; background: white; border-right: 1px solid #e2e8f0;
  padding: 24px 16px; display: flex; flex-direction: column;
  position: fixed; height: 100vh; z-index: 1000;
}
.logo { display: flex; align-items: center; gap: 10px; font-size: 18px; font-weight: 600; color: #1e293b; margin-bottom: 32px; padding: 0 12px; }
nav { flex: 1; display: flex; flex-direction: column; gap: 4px; }
nav a { display: flex; align-items: center; gap: 10px; padding: 12px 16px; color: #64748b; text-decoration: none; border-radius: 8px; font-size: 14px; }
nav a:hover { background: #f1f5f9; color: #1e293b; }
nav a.router-link-active { background: #6366f1; color: white; }
.nav-icon { font-size: 16px; }
.logout { padding: 12px; background: #f1f5f9; border: none; border-radius: 8px; color: #64748b; cursor: pointer; }
.logout:hover { background: #e2e8f0; }
main { flex: 1; padding: 32px; }
main.with-sidebar { margin-left: 240px; }
main.full-page { padding: 0; }

/* 平板：侧边栏收窄为图标模式 */
@media (min-width: 769px) and (max-width: 1024px) {
  .sidebar { width: 64px; padding: 24px 8px; align-items: center; }
  .logo-text, .nav-label { display: none; }
  .logo { padding: 0; justify-content: center; }
  nav a { justify-content: center; padding: 12px; }
  main.with-sidebar { margin-left: 64px; }
}

/* 移动端：侧边栏隐藏，汉堡菜单触发 */
@media (max-width: 768px) {
  .hamburger { display: block; }
  .overlay { display: block; }
  .sidebar { transform: translateX(-100%); transition: transform 0.3s ease; }
  .sidebar.open { transform: translateX(0); }
  main.with-sidebar { margin-left: 0; padding: 24px 16px; padding-top: 60px; }
}
</style>
