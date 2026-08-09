import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const EVENT_COLORS: Record<string, string> = {
  person: '#ef4444',
  intrusion: '#dc2626',
  car: '#f97316',
  truck: '#f97316',
  bus: '#f97316',
  motorcycle: '#f97316',
  bicycle: '#eab308',
  fire: '#3b82f6',
  smoke: '#3b82f6',
  motion: '#22c55e',
  dog: '#a855f7',
  backpack: '#94a3b8',
}

export const PRIORITY_COLOR: Record<string, string> = {
  critical: '#f0435a',
  high: '#f0a040',
  medium: '#4aa3ff',
  low: '#8b9bb0',
}

export function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
