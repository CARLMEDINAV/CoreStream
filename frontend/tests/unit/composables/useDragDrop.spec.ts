import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useDragDrop } from '../../../src/composables/useDragDrop'

describe('useDragDrop Composable', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Limpiar estado global del singleton antes de cada test
    const { dragEnd } = useDragDrop()
    dragEnd()
  })

  afterEach(() => {
    vi.clearAllTimers()
    useDragDrop().dragEnd()
    vi.useRealTimers()
  })

  it('debe establecer el estado correctamente al iniciar el arrastre', () => {
    const { dragStart, dragItem, dragType, isDragging } = useDragDrop()
    const mockEpic = { id: 'epic-123', title: 'Test Epic' }
    
    dragStart(mockEpic, 'epic')
    // espera los dos frames usados para capturar la imagen del arrastre
    expect(isDragging.value).toBe(false)
    vi.advanceTimersToNextFrame()
    expect(isDragging.value).toBe(false)
    vi.advanceTimersToNextFrame()
    
    expect(isDragging.value).toBe(true)
    expect(dragItem.value?.id).toBe('epic-123')
    expect(dragType.value).toBe('epic')
  })

  it('debe retornar DropResult válido al soltar un item compatible', () => {
    const { dragStart, drop } = useDragDrop()
    const mockTicket = { id: 'ticket-1' }
    const mockEvent = { preventDefault: vi.fn(), stopPropagation: vi.fn() } as any

    dragStart(mockTicket, 'ticket')
    
    // Intentar soltar un ticket en una épica (según lógica permitida en el README)
    const result = drop(mockEvent, 'target-epic-id', 'epic')
    
    expect(result).not.toBeNull()
    expect(result?.type).toBe('ticket')
    expect(result?.targetId).toBe('target-epic-id')
  })

  it('debe limpiar el estado global al finalizar (dragEnd)', () => {
    const { dragStart, dragEnd, isDragging, dragItem, dragType } = useDragDrop()
    
    dragStart({ id: '1' }, 'ticket')
    dragEnd()
    
    expect(isDragging.value).toBe(false)
    expect(dragItem.value).toBeNull()
    expect(dragType.value).toBeNull()
  })
})
