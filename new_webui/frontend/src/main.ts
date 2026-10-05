import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './app/router'
import { installSessionWatch } from './stores/auth'
import 'vue-sonner/style.css'
import './assets/styles/main.css'

const app = createApp(App).use(createPinia()).use(router)

// A session that ends under an open page (idle limit, account disabled, signed
// out elsewhere) lands on sign-in with the page it was on, to come back to.
installSessionWatch(() => {
  const here = router.currentRoute.value.fullPath
  void router.push({ name: 'login', query: { next: here } })
})

app.mount('#app')
