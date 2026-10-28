<template>
    <div id="app" style="height: 100%;">
        <router-view/>
    </div>
</template>

<script>
export default {
    name: 'App'
}
</script>

<style>
 #app {
    font-family: 'Segoe UI', Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
 }

 html,
body {
    overscroll-behavior-y: contain;
}
</style>
