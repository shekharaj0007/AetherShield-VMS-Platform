import { create } from 'zustand'

type AppState = {
  gridSize: 1 | 2 | 4 | 9 | 16
  selectedCameraId: number | null
  playbackEventId: number | null
  setGridSize: (n: 1 | 2 | 4 | 9 | 16) => void
  setSelectedCameraId: (id: number | null) => void
  setPlaybackEventId: (id: number | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  gridSize: 4,
  selectedCameraId: null,
  playbackEventId: null,
  setGridSize: (gridSize) => set({ gridSize }),
  setSelectedCameraId: (selectedCameraId) => set({ selectedCameraId }),
  setPlaybackEventId: (playbackEventId) => set({ playbackEventId }),
}))
