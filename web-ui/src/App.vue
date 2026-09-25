<template>
  <div
    class="h-screen flex flex-col bg-background text-foreground overflow-hidden"
  >
    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <header
      class="h-12 shrink-0 flex items-center px-3 gap-3 border-b border-border bg-background/95 backdrop-blur z-50"
    >
      <!-- Sidebar toggle -->
      <button
        @click="sidebarCollapsed = !sidebarCollapsed"
        class="p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-[background-color,color,transform] duration-150 active:scale-[0.97] shrink-0"
      >
        <PanelLeft :size="16" />
      </button>

      <!-- Brand -->
      <div class="flex items-center gap-2 shrink-0">
        <div
          class="w-7 h-7 rounded-lg flex items-center justify-center bg-foreground/10 border border-border"
        >
          <Bot :size="14" class="text-foreground" />
        </div>
        <span class="text-sm font-semibold hidden sm:block">AMR Control</span>
      </div>

      <Separator orientation="vertical" class="h-5 hidden sm:block" />

      <!-- ── Mode Toggle: Mapping / Navigation ── -->
      <div
        class="flex items-center gap-0.5 p-0.5 rounded-lg bg-muted border border-border shrink-0"
      >
        <button
          class="flex items-center gap-1.5 px-3 h-7 rounded-md text-xs font-semibold transition-[background-color,color,box-shadow] duration-150 active:scale-[0.97]"
          :class="
            store.appMode === 'navigation'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          "
          @click="switchMode('navigation')"
        >
          <Navigation2 :size="12" />
          <span class="hidden sm:inline">Navigation</span>
        </button>
        <button
          class="flex items-center gap-1.5 px-3 h-7 rounded-md text-xs font-semibold transition-[background-color,color,box-shadow] duration-150 active:scale-[0.97]"
          :class="
            store.appMode === 'mapping'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          "
          @click="switchMode('mapping')"
        >
          <ScanLine :size="12" />
          <span class="hidden sm:inline">Mapping</span>
        </button>
      </div>

      <Separator orientation="vertical" class="h-5 hidden sm:block" />

      <!-- Pose strip -->
      <div class="hidden lg:flex items-center gap-1 text-xs font-data">
        <span class="text-muted-foreground">X</span>
        <span
          class="text-foreground font-medium tabular-nums w-14 text-right"
          >{{ poseX }}</span
        >
        <span class="text-muted-foreground ml-2">Y</span>
        <span
          class="text-foreground font-medium tabular-nums w-14 text-right"
          >{{ poseY }}</span
        >
        <span class="text-muted-foreground ml-2">θ</span>
        <span class="text-foreground font-medium tabular-nums w-14 text-right"
          >{{ poseTheta }}°</span
        >
      </div>

      <div class="flex-1" />

      <!-- Available / Busy badge -->
      <Badge
        :variant="store.isBusy ? 'destructive' : 'default'"
        class="hidden sm:flex text-[10px] font-mono uppercase"
      >
        <span
          v-if="store.isBusy"
          class="w-1.5 h-1.5 rounded-full bg-white animate-pulse mr-1.5"
        />
        {{ store.availabilityLabel }}
      </Badge>

      <!-- Nav status badge -->
      <Badge
        :variant="statusVariant"
        class="hidden sm:flex text-[10px] font-mono uppercase"
      >
        {{ store.navStatus.replace(/_/g, " ") }}
      </Badge>

      <!-- Battery -->
      <div
        v-if="store.batteryPercent !== null"
        class="hidden sm:flex items-center gap-1.5 text-xs"
      >
        <div
          class="w-6 h-3 rounded-sm border flex items-center px-[1px]"
          :class="batteryBorderClass"
        >
          <div
            class="h-1.5 rounded-[1px] transition-all duration-500"
            :class="batteryFillClass"
            :style="{ width: Math.max(store.batteryPercent, 4) + '%' }"
          />
        </div>
        <span class="font-data font-medium" :class="batteryTextClass">
          {{ store.batteryPercent }}%<span
            v-if="store.batteryCharging"
            class="text-amr-ok ml-0.5"
            >⚡</span
          >
        </span>
        <span
          v-if="store.batteryVoltage !== null"
          class="font-data text-[10px] text-muted-foreground"
        >{{ store.batteryVoltage.toFixed(1) }}V</span>
      </div>

      <!-- ROS connection -->
      <div
        class="flex items-center gap-1.5 text-xs"
        :class="store.rosConnected ? 'text-amr-ok' : 'text-muted-foreground'"
      >
        <span
          class="w-2 h-2 rounded-full shrink-0"
          :class="
            store.rosConnected
              ? 'bg-amr-ok animate-glow-ok'
              : 'bg-muted-foreground'
          "
        />
        <span class="hidden sm:inline font-medium">{{
          store.rosConnected ? "ONLINE" : "OFFLINE"
        }}</span>
      </div>

      <!-- E-STOP — selalu merah, tidak bisa disabled agar reflex tetap jalan -->
      <button
        class="estop-btn shrink-0"
        :class="store.rosConnected ? 'estop-btn--active' : 'estop-btn--offline'"
        @click="emergencyStop"
        title="Emergency Stop"
      >
        <OctagonX :size="14" />
        <span class="hidden sm:inline">E-STOP</span>
      </button>
    </header>

    <!-- ── Body ──────────────────────────────────────────────────────────────── -->
    <div class="flex-1 min-h-0 flex overflow-hidden relative">
      <!-- ── Sidebar ───────────────────────────────────────────────────────── -->
      <AppSidebar
        :items="navItems"
        :active="activeTab"
        :collapsed="sidebarCollapsed"
        :connected="store.rosConnected"
        @select="activeTab = $event"
      />

      <!-- ── Content Area ──────────────────────────────────────────────────── -->
      <main class="flex-1 min-w-0 min-h-0 flex gap-3 p-3 overflow-hidden">
        <!-- ── Map Canvas (square, collapsible) ────────────────────────────── -->
        <div
          class="shrink-0 flex flex-col rounded-xl border border-border overflow-hidden bg-background/50 shadow-lg"
        >
          <!-- Map header bar -->
          <div
            class="flex items-center gap-2 h-8 px-3 bg-muted/40 border-b border-border shrink-0"
          >
            <MapIcon :size="11" class="text-muted-foreground shrink-0" />
            <span
              class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex-1"
              >Map View</span
            >
            <span
              class="text-[10px] text-muted-foreground/40 font-data tabular-nums"
              >Auto</span
            >
            <button
              class="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-[background-color,color,transform] duration-150 active:scale-[0.97] ml-1"
              :title="mapMinimized ? 'Expand map' : 'Minimize map'"
              @click="mapMinimized = !mapMinimized"
            >
              <Minus v-if="!mapMinimized" :size="12" />
              <Maximize2 v-if="mapMinimized" :size="12" />
            </button>
          </div>

          <!-- Map canvas (square, fills viewport height) -->
          <div
            v-show="!mapMinimized"
            class="relative"
            :style="{
              width: 'calc(100vw - 39rem)',
              height: 'calc(100vh - 6.5rem)',
            }"
          >
            <MapView
              class="w-full h-full"
              @destination-click="onDestinationClick"
              @dock-placed="onDockPlaced"
            />

            <!-- ── Floating E-STOP di map ── -->
            <button
              class="absolute bottom-5 left-4 z-[1001] estop-float"
              :class="store.rosConnected ? 'estop-float--active' : 'estop-float--offline'"
              @click="emergencyStop"
              title="Emergency Stop"
            >
              <!-- pulse ring saat robot bergerak -->
              <span
                v-if="store.rosConnected && store.isBusy"
                class="absolute inset-0 rounded-full bg-red-500 animate-ping opacity-40"
              />
              <OctagonX :size="20" />
              <span class="text-xs font-black tracking-widest leading-none">STOP</span>
            </button>
          </div>

          <!-- Minimized state -->
          <div
            v-if="mapMinimized"
            class="flex items-center justify-center py-6 text-muted-foreground text-xs gap-2"
            :style="{ width: 'calc(100vw - 28rem)' }"
          >
            <MapIcon :size="13" />
            Map minimized — klik tombol expand untuk tampilkan
          </div>
        </div>

        <!-- ── Panel ──────────────────────────────────────────────────────── -->
        <div class="flex-1 min-w-0 min-h-0 flex flex-col">
          <Card
            class="flex-1 min-h-0 flex flex-col bg-background/92 backdrop-blur-md border-border shadow-2xl overflow-hidden"
          >
            <ScrollArea class="flex-1 min-h-0">
              <div class="p-3">
                <!-- Overview ──────────────────────────────────────────────── -->
                <template v-if="activeTab === 'overview'">
                  <!-- Connection -->
                  <div
                    class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5 mb-2"
                  >
                    <Wifi :size="10" /> ROS Connection
                  </div>
                  <div class="flex gap-1.5 mb-4">
                    <div
                      class="flex-1 flex items-center rounded-md border border-input bg-transparent px-3 py-1 text-xs font-data min-w-0"
                      aria-readonly="true"
                    >
                      <span class="truncate">{{ store.rosUrl || 'Belum dikonfigurasi' }}</span>
                    </div>
                    <Button
                      size="sm"
                      class="text-xs h-8 px-3"
                      :variant="store.rosConnected ? 'destructive' : 'default'"
                      :disabled="!store.rosConfigValid && !store.rosConnected"
                      @click="toggleConnection"
                    >
                      {{ store.rosConnected ? "Disc." : "Connect" }}
                    </Button>
                  </div>
                  <p v-if="store.rosConfigError" class="text-xs text-destructive mb-4">
                    {{ store.rosConfigError }}
                  </p>

                  <Separator class="mb-4" />

                  <!-- Pose cards -->
                  <div
                    class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase mb-2"
                  >
                    Robot Pose
                  </div>
                  <div class="grid grid-cols-3 gap-2 mb-4">
                    <div
                      v-for="(val, key) in poseDisplay"
                      :key="key"
                      class="rounded-lg border border-border bg-card px-2 py-2.5 text-center"
                    >
                      <div
                        class="text-[9px] text-muted-foreground/50 uppercase tracking-widest mb-1.5 font-medium"
                      >
                        {{ key }}
                      </div>
                      <div class="text-base font-data font-bold text-amr-data tabular-nums leading-none">
                        {{ val }}
                      </div>
                      <div class="text-[9px] text-muted-foreground/40 mt-1.5">
                        {{ key === "θ" ? "deg" : "m" }}
                      </div>
                    </div>
                  </div>

                  <Separator class="mb-4" />

                  <!-- Status -->
                  <div
                    class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase mb-2"
                  >
                    Status
                  </div>
                  <div
                    class="rounded-lg border border-border bg-card p-3 space-y-2 mb-4"
                  >
                    <div class="flex items-center justify-between">
                      <span class="text-xs text-muted-foreground"
                        >Navigation</span
                      >
                      <Badge
                        :variant="statusVariant"
                        class="text-[10px] font-mono uppercase"
                      >
                        {{ store.navStatus.replace(/_/g, " ") }}
                      </Badge>
                    </div>
                    <div v-if="store.missionRunning" class="space-y-1">
                      <div
                        class="flex justify-between text-xs text-muted-foreground"
                      >
                        <span
                          >Waypoint {{ store.currentWaypointIndex + 1 }} /
                          {{ store.waypoints.length }}</span
                        >
                        <span>{{ missionProgress }}%</span>
                      </div>
                      <Progress :model-value="missionProgress" class="h-1.5" />
                    </div>
                    <div class="flex items-center justify-between">
                      <span class="text-xs text-muted-foreground">Docking</span>
                      <Badge
                        :variant="dockVariant"
                        class="text-[10px] font-mono uppercase"
                      >
                        {{ store.dockingStatus }}
                      </Badge>
                    </div>
                  </div>

                  <Separator class="mb-4" />

                  <!-- AMCL Initial Pose -->
                  <button
                    class="flex items-center justify-between w-full mb-2"
                    @click="showInitPose = !showInitPose"
                  >
                    <div
                      class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase flex items-center gap-1.5"
                    >
                      <LocateFixed :size="10" /> AMCL Init Pose
                    </div>
                    <ChevronDown
                      :size="13"
                      class="text-muted-foreground transition-transform"
                      :class="{ 'rotate-180': showInitPose }"
                    />
                  </button>
                  <template v-if="showInitPose">
                    <div class="grid grid-cols-3 gap-1.5 mb-2">
                      <div v-for="field in initPoseFields" :key="field.key">
                        <Label
                          class="text-[9px] text-muted-foreground uppercase tracking-wider"
                          >{{ field.label }}</Label
                        >
                        <Input
                          v-model.number="initPose[field.key]"
                          type="number"
                          :step="field.step"
                          class="w-full text-xs font-data h-7 mt-0.5 px-2"
                        />
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      class="text-xs w-full h-7 mb-4"
                      :disabled="!store.rosConnected"
                      @click="setInitPose"
                    >
                      Set Initial Pose
                    </Button>
                  </template>

                  <Separator class="mb-4" />

                  <!-- Speed Chart -->
                  <div
                    class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase mb-2"
                  >
                    Velocity
                  </div>
                  <div class="rounded-lg border border-border bg-card p-2 mb-4">
                    <SpeedChart :height="120" />
                  </div>

                  <!-- System stats -->
                  <div
                    class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase mb-2"
                  >
                    System
                  </div>
                  <div
                    class="rounded-lg border border-border bg-card p-3 space-y-2"
                  >
                    <div
                      v-for="(val, key) in statsDisplay"
                      :key="key"
                      class="flex items-center justify-between"
                    >
                      <span class="text-[10px] text-muted-foreground/60 uppercase tracking-wider font-medium">{{ key }}</span>
                      <span class="text-sm font-data font-semibold text-foreground">{{ val }}</span>
                    </div>
                  </div>
                </template>

                <!-- Mapping mode panels -->
                <MappingPanel
                  v-else-if="
                    activeTab === 'mapping' && store.appMode === 'mapping'
                  "
                />

                <!-- Navigation mode panels -->
                <MissionPanel
                  v-else-if="
                    activeTab === 'mission' && store.appMode === 'navigation'
                  "
                  ref="missionPanelRef"
                />
                <DockingPanel
                  v-else-if="
                    activeTab === 'docking' && store.appMode === 'navigation'
                  "
                />
                <SetupPanel
                  v-else-if="
                    activeTab === 'setup' && store.appMode === 'navigation'
                  "
                />
              </div>
            </ScrollArea>
          </Card>
        </div>
      </main>
    </div>

    <!-- ── Offline overlay ──────────────────────────────────────────────────── -->
    <transition name="offline-fade">
      <div
        v-if="!store.rosConnected"
        class="absolute inset-0 z-40 pointer-events-none"
        style="background: rgba(9,9,11,0.55); backdrop-filter: blur(2px);"
      >
        <!-- Banner di tengah bawah -->
        <div class="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-5 py-3 rounded-2xl border border-border/60 bg-background/90 backdrop-blur-md shadow-2xl pointer-events-auto">
          <span class="w-2 h-2 rounded-full bg-muted-foreground/50 shrink-0" />
          <div>
            <p class="text-xs font-semibold text-foreground leading-tight">No robot connection</p>
            <p class="text-[10px] text-muted-foreground leading-tight mt-0.5">
              {{ store.rosConfigError || 'ROS target is configured by VITE_ROS_URL' }}
            </p>
          </div>
          <button
            class="ml-2 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-lg bg-foreground text-background hover:bg-foreground/90 transition-colors duration-150 active:scale-[0.97]"
            @click="activeTab = 'overview'"
          >
            Connect
          </button>
        </div>
      </div>
    </transition>

    <!-- Dialog for Dock Placement -->
    <Dialog v-model:open="showDockDialog">
      <DialogContent class="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Name Dock Station</DialogTitle>
        </DialogHeader>
        <div class="grid gap-4 py-4">
          <div class="grid grid-cols-4 items-center gap-4">
            <Label for="dock-name" class="text-right text-xs">Name</Label>
            <Input
              id="dock-name"
              v-model="dockNameInput"
              class="col-span-3 text-xs"
              @keyup.enter="confirmDockPlacement"
              autofocus
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" size="sm" @click="showDockDialog = false"
            >Cancel</Button
          >
          <Button size="sm" @click="confirmDockPlacement">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Dialog: Confirm Mode Switch -->
    <Dialog v-model:open="showModeDialog" @update:open="onModeDialogOpen">
      <DialogContent class="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <component
              :is="pendingMode === 'mapping' ? ScanLine : Navigation2"
              :size="16"
            />
            Ganti Mode ke {{ pendingMode === 'mapping' ? 'Mapping' : 'Navigation' }}?
          </DialogTitle>
        </DialogHeader>

        <div class="py-2 space-y-4">
          <p class="text-sm text-muted-foreground">
            Ganti ke mode
            <span class="font-semibold text-foreground">{{ pendingMode === 'mapping' ? 'Mapping' : 'Navigation' }}</span>?
          </p>
          <p class="text-xs text-amber-500">
            Semua misi yang sedang berjalan akan dibatalkan.
          </p>

          <div v-if="pendingMode === 'navigation'" class="space-y-1.5">
            <Label class="text-xs font-semibold">Pilih Map</Label>
            <div v-if="mapsLoading" class="flex items-center gap-2 text-xs text-muted-foreground py-1">
              <span class="w-3 h-3 rounded-full border-2 border-t-transparent border-current animate-spin" />
              Memuat daftar map...
            </div>
            <div v-else-if="availableMaps.length === 0" class="rounded-md border border-destructive/50 bg-destructive/5 p-2 text-xs text-destructive">
              Belum ada map tersimpan. Pilih <strong>Mapping</strong> untuk membuat peta dulu.
            </div>
            <select
              v-else
              v-model="selectedMapFile"
              class="w-full text-xs h-8 rounded-md border border-input bg-background px-2 focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="" disabled>-- Pilih map --</option>
              <option v-for="m in availableMaps" :key="m.id" :value="m.yaml_file">
                {{ m.name }} ({{ m.yaml_file }})
              </option>
            </select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" size="sm" @click="showModeDialog = false" :disabled="modeSwitching">
            Batal
          </Button>
          <Button
            size="sm"
            :disabled="modeSwitching || (pendingMode === 'navigation' && (!selectedMapFile || mapsLoading))"
            @click="confirmSwitchMode"
          >
            <span v-if="modeSwitching" class="flex items-center gap-1.5">
              <span class="w-3 h-3 rounded-full border-2 border-t-transparent border-current animate-spin" />
              Switching...
            </span>
            <span v-else>Ya, Ganti Mode</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Dialog: Startup Mode Selection -->
    <Dialog v-model:open="showStartupDialog">
      <DialogContent class="sm:max-w-[420px]" :closeable="false">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2 text-base">
            <Bot :size="16" />
            Pilih Mode Operasi
          </DialogTitle>
        </DialogHeader>

        <div class="py-3 space-y-3">
          <!-- ROS bridge target is build-time configuration and is intentionally read-only. -->
          <div class="rounded-md border border-border bg-muted/30 p-2.5 space-y-1.5">
            <div class="flex items-center justify-between text-[10px] uppercase tracking-widest text-muted-foreground">
              <span>ROS Bridge</span>
              <span
                class="font-semibold"
                :class="store.rosConnected ? 'text-emerald-500' : store.rosConfigError ? 'text-destructive' : 'text-amber-500'"
              >
                {{ store.rosConnected ? 'Connected' : store.rosConfigError ? 'Configuration error' : 'Offline' }}
              </span>
            </div>
            <div class="rounded border border-input bg-background px-2 py-1.5 text-xs font-mono break-all">
              {{ store.rosUrl || 'VITE_ROS_URL belum dikonfigurasi' }}
            </div>
            <p v-if="store.rosConfigError" class="text-[11px] text-destructive">
              {{ store.rosConfigError }}
            </p>
            <p v-else class="text-[11px] text-muted-foreground">
              Target ROS ditentukan melalui environment frontend.
            </p>
          </div>

          <!-- Mode selector cards -->
          <div class="grid grid-cols-2 gap-3">
            <button
              class="flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all"
              :class="startupMode === 'mapping'
                ? 'border-amber-500 bg-amber-500/10 text-amber-400'
                : 'border-border hover:border-muted-foreground text-muted-foreground hover:text-foreground'"
              @click="startupMode = 'mapping'; startupMapFile = ''"
            >
              <ScanLine :size="22" />
              <div class="text-xs font-semibold">Mapping</div>
              <div class="text-[10px] text-center leading-tight opacity-70">
                Buat peta baru dengan SLAM
              </div>
            </button>
            <button
              class="flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all"
              :class="startupMode === 'navigation'
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border hover:border-muted-foreground text-muted-foreground hover:text-foreground'"
              @click="onStartupNavSelect"
            >
              <Navigation2 :size="22" />
              <div class="text-xs font-semibold">Navigation</div>
              <div class="text-[10px] text-center leading-tight opacity-70">
                Navigasi dengan peta tersimpan
              </div>
            </button>
          </div>

          <!-- Map selector (hanya muncul kalau navigation dipilih) -->
          <template v-if="startupMode === 'navigation'">
            <div class="space-y-1.5">
              <Label class="text-xs font-semibold">Pilih Map</Label>
              <div v-if="mapsLoading" class="flex items-center gap-2 text-xs text-muted-foreground py-1">
                <span class="w-3 h-3 rounded-full border-2 border-t-transparent border-current animate-spin" />
                Memuat daftar map...
              </div>
              <div v-else-if="availableMaps.length === 0" class="rounded-md border border-destructive/50 bg-destructive/5 p-2 text-xs text-destructive">
                Belum ada map tersimpan. Pilih <strong>Mapping</strong> untuk membuat peta dulu.
              </div>
              <select
                v-else
                v-model="startupMapFile"
                class="w-full text-xs h-8 rounded-md border border-input bg-background px-2 focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="" disabled>-- Pilih map --</option>
                <option v-for="m in availableMaps" :key="m.id" :value="m.yaml_file">
                  {{ m.name }} ({{ m.yaml_file }})
                </option>
              </select>
            </div>
          </template>
        </div>

        <DialogFooter>
          <Button
            class="w-full"
            size="sm"
            :disabled="!startupMode || (startupMode === 'navigation' && !startupMapFile) || modeSwitching"
            @click="confirmStartup"
          >
            <span v-if="modeSwitching" class="flex items-center gap-1.5">
              <span class="w-3 h-3 rounded-full border-2 border-t-transparent border-current animate-spin" />
              Memulai...
            </span>
            <span v-else>Mulai</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Toast overlay -->
    <Toaster position="top-right" richColors />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { useRobotStore } from "@/stores/robot";
import { useROS } from "@/composables/useROS";
import { useAPI } from "@/composables/useAPI";
import { useMapMode } from "@/composables/useMapMode";
import { useSystemStats } from "@/composables/useSystemStats";
import {
  LayoutDashboard,
  Route,
  Settings2,
  PlugZap,
  LocateFixed,
  ChevronDown,
  ScanLine,
  Wifi,
  PanelLeft,
  Bot,
  OctagonX,
  Navigation2,
  Map as MapIcon,
  Maximize2,
  Minus,
} from "lucide-vue-next";
import { Toaster, toast } from "vue-sonner";
import "vue-sonner/style.css";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

import AppSidebar from "@/components/ui/sidebar/AppSidebar.vue";
import MapView from "@/components/MapView.vue";
import MissionPanel from "@/components/MissionPanel.vue";
import MappingPanel from "@/components/MappingPanel.vue";
import SetupPanel from "@/components/SetupPanel.vue";
import DockingPanel from "@/components/DockingPanel.vue";
import SpeedChart from "@/components/charts/SpeedChart.vue";

const store = useRobotStore();
const ros = useROS();
const api = useAPI();
const mapMode = useMapMode();
const stats = useSystemStats();

const missionPanelRef = ref(null);
const activeTab = ref("overview");
const sidebarCollapsed = ref(false);
const mapMinimized = ref(false);
const showInitPose = ref(false);
const initPose = ref({ x: 0, y: 0, thetaDeg: 0 });

const showDockDialog = ref(false);
const dockNameInput = ref("");
const pendingDockPlacement = ref(null);

const showModeDialog = ref(false);
const pendingMode = ref(null);
const modeSwitching = ref(false);
const availableMaps = ref([]);
const selectedMapFile = ref("");
const mapsLoading = ref(false);

// Startup dialog
const showStartupDialog = ref(false);
const startupMode = ref("");
const startupMapFile = ref("");

async function onModeDialogOpen(open) {
  if (!open || pendingMode.value !== "navigation") return;
  mapsLoading.value = true;
  selectedMapFile.value = "";
  try {
    availableMaps.value = await api.get("/maps");
    // Auto-select jika hanya ada satu map
    if (availableMaps.value.length === 1) {
      selectedMapFile.value = availableMaps.value[0].yaml_file;
    }
  } catch {
    availableMaps.value = [];
  } finally {
    mapsLoading.value = false;
  }
}

const initPoseFields = [
  { key: "x", label: "X", step: 0.1 },
  { key: "y", label: "Y", step: 0.1 },
  { key: "thetaDeg", label: "θ°", step: 5 },
];

// Semua item yang tersedia per mode
const NAV_ITEMS_NAVIGATION = [
  { id: "overview", label: "Overview", short: "Home", icon: LayoutDashboard },
  { id: "mission", label: "Mission", short: "Mission", icon: Route },
  { id: "docking", label: "Docking", short: "Dock", icon: PlugZap },
  { id: "setup", label: "Setup", short: "Setup", icon: Settings2 },
];
const NAV_ITEMS_MAPPING = [
  { id: "overview", label: "Overview", short: "Home", icon: LayoutDashboard },
  { id: "mapping", label: "Mapping", short: "Map", icon: ScanLine },
];

const navItems = computed(() =>
  store.appMode === "mapping" ? NAV_ITEMS_MAPPING : NAV_ITEMS_NAVIGATION,
);

function switchMode(mode) {
  // Kalau sudah di mode yang sama, skip
  if (store.appMode === mode) return;
  // Tampilkan confirm dialog
  pendingMode.value = mode;
  showModeDialog.value = true;
}

async function confirmSwitchMode() {
  if (!pendingMode.value) return;
  modeSwitching.value = true;
  try {
    const mode = pendingMode.value;
    const backendMode = mode === "mapping" ? "slam" : "navigation";
    const payload = { mode: backendMode };
    if (backendMode === "navigation" && selectedMapFile.value) {
      payload.map_file = `/maps/${selectedMapFile.value}`;
    }
    const response = await api.post("/mode/switch", payload);
    store.setAppMode(mode);
    // Reset tab kalau tab aktif tidak ada di mode baru
    const available = mode === "mapping" ? NAV_ITEMS_MAPPING : NAV_ITEMS_NAVIGATION;
    if (!available.find((i) => i.id === activeTab.value)) {
      activeTab.value = mode === "mapping" ? "mapping" : "overview";
    }
    mapMode.setMode("view");
    toast.success(
      response?.message ||
        `Mode ${mode === "mapping" ? "Mapping" : "Navigation"} aktif`,
    );
    showModeDialog.value = false;
  } catch (err) {
    toast.error(`Gagal ganti mode: ${err.message}`);
  } finally {
    modeSwitching.value = false;
    pendingMode.value = null;
  }
}

// ── Pose ──────────────────────────────────────────────────────────────────────
const poseX = computed(() => store.robotPose.x.toFixed(2));
const poseY = computed(() => store.robotPose.y.toFixed(2));
const poseTheta = computed(() =>
  ((store.robotPose.theta * 180) / Math.PI).toFixed(1),
);

const poseDisplay = computed(() => ({
  X: poseX.value,
  Y: poseY.value,
  θ: poseTheta.value,
}));

// ── Mission progress ──────────────────────────────────────────────────────────
const missionProgress = computed(() => {
  if (!store.waypoints.length) return 0;
  return Math.round(
    (store.currentWaypointIndex / store.waypoints.length) * 100,
  );
});

// ── Stats ─────────────────────────────────────────────────────────────────────
const statsDisplay = computed(() => ({
  CPU: stats.cpu,
  Memory: stats.mem,
  Latency: stats.latency,
}));

// ── Map mode label ────────────────────────────────────────────────────────────
const mapModeLabel = computed(() => {
  const m = mapMode.mapMode?.value;
  if (!m || m === "navigate") return null;
  const labels = {
    waypoint: "📍 Click to add waypoint",
    keepout: "🚫 Click to draw keepout zone",
    initial_pose: "🎯 Click+drag to set initial pose",
    destination: "🏁 Click to add destination",
    dock_placement: "⚓ Click dock pos, then approach pos",
  };
  return labels[m] || m;
});

// ── Badge variants ────────────────────────────────────────────────────────────
const statusVariant = computed(() => {
  const s = store.navStatus;
  if (s === "error") return "destructive";
  if (s === "navigating" || s === "following_waypoints") return "secondary";
  return "outline";
});

const dockVariant = computed(() => {
  const s = store.dockingStatus;
  if (s === "error") return "destructive";
  if (s === "docked") return "default";
  return "outline";
});

// ── Battery ───────────────────────────────────────────────────────────────────
const batteryFillClass = computed(() => {
  if (store.batteryCharging) return "bg-amr-ok";
  const p = store.batteryPercent;
  if (p === null) return "bg-muted-foreground";
  if (p <= 10) return "bg-amr-danger animate-pulse";
  if (p <= 20) return "bg-amr-danger";
  if (p <= 40) return "bg-amr-warning";
  return "bg-amr-ok";
});
const batteryBorderClass = computed(() => {
  if (store.batteryCharging) return "border-amr-ok";
  if (store.batteryPercent !== null && store.batteryPercent <= 20)
    return "border-amr-danger";
  return "border-muted-foreground/50";
});
const batteryTextClass = computed(() => {
  if (store.batteryCharging) return "text-amr-ok";
  const p = store.batteryPercent;
  if (p !== null && p <= 10) return "text-amr-danger font-bold";
  if (p !== null && p <= 20) return "text-amr-danger";
  if (p !== null && p <= 40) return "text-amr-warning";
  return "text-foreground";
});

// ── Actions ───────────────────────────────────────────────────────────────────
function toggleConnection() {
  if (store.rosConnected) {
    ros.disconnect();
  } else if (store.rosConfigValid) {
    ros.connect(store.rosUrl);
  }
}

function setInitPose() {
  ros.setInitialPose(
    initPose.value.x,
    initPose.value.y,
    (initPose.value.thetaDeg * Math.PI) / 180,
  );
}

function emergencyStop() {
  ros.cancelNavigation();
  store.stopMission();
  toast.error("Emergency stop activated!");
}

function onDestinationClick(x, y, yaw = 0) {
  if (activeTab.value !== "mission") activeTab.value = "mission";
  setTimeout(() => missionPanelRef.value?.onMapClick(x, y, yaw), 0);
}

async function onDockPlaced({ x, y, yaw, approach_x, approach_y }) {
  pendingDockPlacement.value = { x, y, yaw, approach_x, approach_y };
  dockNameInput.value = `Dock ${store.dockStations.length + 1}`;
  showDockDialog.value = true;
}

async function confirmDockPlacement() {
  if (!dockNameInput.value.trim() || !pendingDockPlacement.value) return;

  const { x, y, yaw, approach_x, approach_y } = pendingDockPlacement.value;
  const name = dockNameInput.value.trim();

  showDockDialog.value = false;
  pendingDockPlacement.value = null;

  try {
    const dock = await api.post("/docks", {
      map_id: store.activeMapId,
      name,
      target: { x, y, yaw },
      approach: { x: approach_x, y: approach_y, yaw },
    });
    store.addDockStation(dock);
    store.setAutoDockTargetId(dock.id);
    // Register dock ke robot via /station_config (station_type 3 = Charging/Dock)
    await ros.configStation({
      station_id: dock.name,
      station_type: 3,
      action: 1,
      x: dock.target.x,
      y: dock.target.y,
      yaw: dock.target.yaw,
    });
    toast.success(`Dock station "${name}" saved!`);
  } catch (err) {
    toast.error("Failed to save dock: " + err.message);
  }
}

// ── Auto-dock on low battery ──────────────────────────────────────────────────
watch(
  () => store.batteryPercent,
  (val) => {
    if (val === null) return;
    if (
      !store.autoDockEnabled ||
      store.batteryCharging ||
      store.dockingStatus !== "idle"
    )
      return;
    if (val > store.lowBatteryThreshold) return;
    const target = store.dockStations.find(
      (d) => d.id == store.autoDockTargetId,
    );
    if (target) {
      toast.warning(`Battery low (${val}%). Auto-docking to ${target.name}...`);
      ros.cancelNavigation();
      store.stopMission();
      ros.sendToDock(target);
      store.setDockingStatus("docking");
    }
  },
);

async function syncModeFromBackend(isStartup = false) {
  try {
    const data = await api.get("/mode");
    const isFirstRun = !data.mode || data.mode === "navigation" && !data.map_file;

    // Saat pertama load: kalau belum pernah di-set (fresh install), tampilkan startup dialog
    if (isStartup && isFirstRun) {
      mapsLoading.value = true;
      try {
        availableMaps.value = await api.get("/maps");
      } catch {
        availableMaps.value = [];
      } finally {
        mapsLoading.value = false;
      }
      startupMode.value = "";
      startupMapFile.value = "";
      showStartupDialog.value = true;
      return;
    }

    // Mode sudah pernah di-set — langsung apply
    const uiMode = data.mode === "slam" ? "mapping" : "navigation";
    _applyMode(uiMode);
  } catch {
    // backend belum ready, tampilkan startup dialog
    if (isStartup) showStartupDialog.value = true;
  }
}

function _applyMode(uiMode) {
  store.setAppMode(uiMode);
  const available = uiMode === "mapping" ? NAV_ITEMS_MAPPING : NAV_ITEMS_NAVIGATION;
  if (!available.find((i) => i.id === activeTab.value)) {
    activeTab.value = uiMode === "mapping" ? "mapping" : "overview";
  }
  mapMode.setMode("view");
}

async function onStartupNavSelect() {
  startupMode.value = "navigation";
  if (availableMaps.value.length === 0) {
    mapsLoading.value = true;
    try {
      availableMaps.value = await api.get("/maps");
      if (availableMaps.value.length === 1) startupMapFile.value = availableMaps.value[0].yaml_file;
    } catch {
      availableMaps.value = [];
    } finally {
      mapsLoading.value = false;
    }
  }
}

async function confirmStartup() {
  if (!startupMode.value) return;
  modeSwitching.value = true;
  try {
    const backendMode = startupMode.value === "mapping" ? "slam" : "navigation";
    const payload = { mode: backendMode };
    if (backendMode === "navigation" && startupMapFile.value) {
      payload.map_file = `/maps/${startupMapFile.value}`;
    }
    await api.post("/mode/switch", payload);
    _applyMode(startupMode.value);
    showStartupDialog.value = false;
    toast.success(`Mode ${startupMode.value === "mapping" ? "Mapping" : "Navigation"} dimulai`);
  } catch (err) {
    toast.error(`Gagal memulai: ${err.message}`);
  } finally {
    modeSwitching.value = false;
  }
}

onMounted(async () => {
  if (store.rosConfigValid) {
    ros.connect(store.rosUrl);
  } else {
    console.warn("[App] ROS bridge is not configured:", store.rosConfigError);
  }
  try {
    const maps = await api.get("/maps");
    store.setMaps(maps);
  } catch (err) {
    console.warn("[App] Could not fetch maps:", err.message);
  }
  // Cek mode dari backend — tampilkan startup dialog kalau fresh install
  await syncModeFromBackend(true);
  stats.startPolling(api.get);
  document.documentElement.classList.add("dark");
});

// Re-sync setiap kali ROS connect (misal setelah mode switch selesai restart)
watch(
  () => store.rosConnected,
  async (connected) => {
    if (connected) await syncModeFromBackend(false);
  },
);

onUnmounted(() => stats.stopPolling());
</script>

<style scoped>
/* ── E-STOP header button ───────────────────────────────────────────── */
.estop-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0 0.75rem;
  height: 2rem;
  border-radius: 0.5rem;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  border: 1.5px solid transparent;
  transition: transform 100ms cubic-bezier(0.23, 1, 0.32, 1),
              background-color 100ms cubic-bezier(0.23, 1, 0.32, 1),
              box-shadow 100ms cubic-bezier(0.23, 1, 0.32, 1);
}

.estop-btn:active {
  transform: scale(0.95);
}

.estop-btn--active {
  background-color: hsl(0 84.2% 60.2%);
  color: white;
  border-color: hsl(0 84.2% 70%);
  box-shadow: 0 0 0 0 hsl(0 84.2% 60.2% / 0);
}

.estop-btn--active:hover {
  background-color: hsl(0 84.2% 52%);
  box-shadow: 0 0 12px hsl(0 84.2% 60.2% / 0.4);
}

.estop-btn--offline {
  background-color: hsl(0 0% 14.9%);
  color: hsl(0 0% 40%);
  border-color: hsl(0 0% 20%);
  cursor: not-allowed;
}

/* ── Floating E-STOP di map ─────────────────────────────────────────── */
.estop-float {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: 2px solid transparent;
  font-weight: 900;
  transition: transform 100ms cubic-bezier(0.23, 1, 0.32, 1),
              box-shadow 150ms cubic-bezier(0.23, 1, 0.32, 1);
}

.estop-float:active {
  transform: scale(0.92);
}

.estop-float--active {
  background-color: hsl(0 84.2% 55%);
  border-color: hsl(0 84.2% 70%);
  color: white;
  box-shadow: 0 4px 20px hsl(0 84.2% 55% / 0.5), 0 0 0 3px hsl(0 84.2% 55% / 0.15);
}

.estop-float--active:hover {
  box-shadow: 0 4px 28px hsl(0 84.2% 55% / 0.7), 0 0 0 5px hsl(0 84.2% 55% / 0.2);
}

.estop-float--offline {
  background-color: hsl(0 0% 10%);
  border-color: hsl(0 0% 18%);
  color: hsl(0 0% 35%);
  cursor: not-allowed;
}

/* ── Offline fade transition ────────────────────────────────────────── */
.offline-fade-enter-active {
  transition: opacity 250ms cubic-bezier(0.23, 1, 0.32, 1);
}
.offline-fade-leave-active {
  transition: opacity 180ms cubic-bezier(0.23, 1, 0.32, 1);
}
.offline-fade-enter-from,
.offline-fade-leave-to {
  opacity: 0;
}
</style>
