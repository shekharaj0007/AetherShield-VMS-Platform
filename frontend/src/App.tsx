import { Routes, Route } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { LivePage } from '@/pages/LivePage'
import { PlaybackPage } from '@/pages/PlaybackPage'
import { EventsPage } from '@/pages/EventsPage'
import { SearchPage } from '@/pages/SearchPage'
import { IncidentsPage } from '@/pages/IncidentsPage'
import { MapPage } from '@/pages/MapPage'
import { ChatPage } from '@/pages/ChatPage'
import { CamerasPage } from '@/pages/CamerasPage'
import { FacesPage } from '@/pages/FacesPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/live" element={<LivePage />} />
        <Route path="/playback" element={<PlaybackPage />} />
        <Route path="/cameras" element={<CamerasPage />} />
        <Route path="/faces" element={<FacesPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Route>
    </Routes>
  )
}
