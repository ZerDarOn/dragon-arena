<template><div class="msg" :class="msg.channel"><span class="sender">{{ msg.sender_id }}</span><span>{{ msg.text }}</span></div></template>
<script setup lang="ts">import type { ChatMessage } from '../../api/types'
defineProps<{ msg: ChatMessage }>()</script>
<style scoped>
.msg { padding: 4px; border-bottom: 1px solid #eee; }
.sender { font-weight: bold; margin-right: 8px; }
.spatial_normal { background: #fff7e6; }
.spatial_shout { background: #fff0f0; font-weight: bold; }
.battle { background: #e6f7ff; }
</style>
