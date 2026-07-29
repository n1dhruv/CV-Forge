import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { UIProvider } from './store/ui'
import './styles/globals.css'
const queryClient=new QueryClient({defaultOptions:{queries:{staleTime:30_000,retry:1}}})
createRoot(document.getElementById('root')!).render(<StrictMode><QueryClientProvider client={queryClient}><UIProvider><BrowserRouter><App/></BrowserRouter></UIProvider></QueryClientProvider></StrictMode>)
