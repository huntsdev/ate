import { createContext, useContext } from 'react'
export const NoticeContext = createContext<(message: string) => void>(() => {})
export const useNotice = () => useContext(NoticeContext)
