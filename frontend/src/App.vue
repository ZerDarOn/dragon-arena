<template>
  <router-view />
  <ToastHost />
  <DiceBoxOverlay />
</template>

<script setup lang="ts">
import ToastHost from './components/ui/ToastHost.vue'
import DiceBoxOverlay from './components/ui/DiceBoxOverlay.vue'
</script>
