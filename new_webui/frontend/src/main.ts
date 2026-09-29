import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './app/router'
import 'vue-sonner/style.css'
import './assets/styles/main.css'

createApp(App).use(createPinia()).use(router).mount('#app')
