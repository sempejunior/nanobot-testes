import { create } from "zustand";

export type ToastType = "success" | "error" | "info";

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastState {
  toasts: Toast[];
  addToast: (type: ToastType, message: string) => void;
  removeToast: (id: string) => void;
}

let counter = 0;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  addToast(type, message) {
    const id = `toast_${++counter}`;
    set({ toasts: [...get().toasts, { id, type, message }] });
    setTimeout(() => get().removeToast(id), 4000);
  },
  removeToast(id) {
    set({ toasts: get().toasts.filter((t) => t.id !== id) });
  },
}));

/** Fire-and-forget toast from anywhere */
export function toast(type: ToastType, message: string) {
  useToastStore.getState().addToast(type, message);
}
