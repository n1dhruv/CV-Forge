import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ClerkProvider } from '@clerk/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { UIProvider } from './store/ui'
import './styles/globals.css'
const queryClient=new QueryClient({defaultOptions:{queries:{staleTime:30_000,retry:1}}})
const clerkPublishableKey=import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
if(!clerkPublishableKey)throw new Error('Missing VITE_CLERK_PUBLISHABLE_KEY. Copy .env.example to .env and add your Clerk publishable key.')
createRoot(document.getElementById('root')!).render(<StrictMode><ClerkProvider publishableKey={clerkPublishableKey}><QueryClientProvider client={queryClient}><UIProvider><BrowserRouter><App/></BrowserRouter></UIProvider></QueryClientProvider></ClerkProvider></StrictMode>)
