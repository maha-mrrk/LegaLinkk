import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import {
  CheckCircle2,
  Eye,
  EyeOff,
  Globe,
  Scale,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

interface LoginForm {
  email: string
  password: string
}

const features = [
  'Analyse juridique intelligente',
  'Détection automatique des risques',
  'Supervision du pipeline IA',
  'Rapports exportables en un clic',
]

export function LoginPage() {
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    defaultValues: {
      email: 'reda.elamrani@legallink.ma',
      password: 'demo1234',
    },
  })

  const onSubmit = async () => {
    await new Promise((r) => setTimeout(r, 500))
    navigate('/dashboard')
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="relative hidden overflow-hidden bg-navy text-white lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div
          className="pointer-events-none absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              'radial-gradient(circle at 20% 20%, #2563EB 0%, transparent 40%), radial-gradient(circle at 80% 80%, #1E3A8A 0%, transparent 45%)',
          }}
        />
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-xl bg-brand">
              <Scale className="size-6" />
            </div>
            <div>
              <p className="text-xl font-bold">LegalLink</p>
              <p className="text-xs uppercase tracking-widest text-slate-400">
                Legal Intelligence
              </p>
            </div>
          </div>
          <h1 className="mt-16 max-w-md text-4xl font-bold leading-tight">
            Analysez vos contrats avec la précision d’un cabinet, à la vitesse de l’IA.
          </h1>
          <ul className="mt-10 space-y-4">
            {features.map((feature) => (
              <li key={feature} className="flex items-center gap-3 text-slate-200">
                <CheckCircle2 className="size-5 text-brand" />
                <span>{feature}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="relative flex items-center gap-2 text-sm text-slate-400">
          <ShieldCheck className="size-4" />
          Données chiffrées · Hébergement sécurisé · Conformité RGPD
        </div>
      </aside>

      <main className="flex items-center justify-center bg-white px-6 py-12">
        <div className="w-full max-w-md animate-[fadeIn_0.4s_ease]">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <div className="flex size-9 items-center justify-center rounded-lg bg-brand text-white">
              <Scale className="size-5" />
            </div>
            <span className="text-lg font-bold text-navy">LegalLink</span>
          </div>

          <div className="mb-8">
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-brand">
              <Sparkles className="size-3.5" />
              Plateforme juridique IA
            </div>
            <h2 className="text-3xl font-bold text-slate-900">Bienvenue !</h2>
            <p className="mt-2 text-sm text-muted">
              Connectez-vous pour accéder à vos analyses et consultations.
            </p>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
            <Input
              label="Adresse e-mail"
              type="email"
              placeholder="vous@cabinet.com"
              error={errors.email?.message}
              {...register('email', {
                required: 'Email requis',
                pattern: {
                  value: /^\S+@\S+$/i,
                  message: 'Email invalide',
                },
              })}
            />
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">
                  Mot de passe
                </label>
                <button
                  type="button"
                  className="text-xs font-medium text-brand hover:underline"
                >
                  Mot de passe oublié ?
                </button>
              </div>
              <Input
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                error={errors.password?.message}
                rightIcon={
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="text-muted hover:text-slate-700"
                    aria-label={showPassword ? 'Masquer' : 'Afficher'}
                  >
                    {showPassword ? (
                      <EyeOff className="size-4" />
                    ) : (
                      <Eye className="size-4" />
                    )}
                  </button>
                }
                {...register('password', {
                  required: 'Mot de passe requis',
                  minLength: { value: 6, message: '6 caractères minimum' },
                })}
              />
            </div>
            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
              {isSubmitting ? 'Connexion…' : 'Se connecter'}
            </Button>
          </form>

          <div className="my-6 flex items-center gap-3 text-xs text-muted">
            <div className="h-px flex-1 bg-border" />
            ou continuer avec
            <div className="h-px flex-1 bg-border" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Button type="button" variant="secondary" className="w-full">
              <GoogleIcon />
              Google
            </Button>
            <Button type="button" variant="secondary" className="w-full">
              <MicrosoftIcon />
              Microsoft
            </Button>
          </div>

          <p className="mt-8 text-center text-sm text-muted">
            Pas encore de compte ?{' '}
            <Link to="/dashboard" className="font-medium text-brand hover:underline">
              Créer un compte
            </Link>
          </p>

          <div className="mt-6 flex items-center justify-center gap-2 text-xs text-muted">
            <Globe className="size-3.5" />
            Français (FR)
          </div>
        </div>
      </main>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#EA4335"
        d="M12 10.2v3.9h5.5c-.2 1.3-1.6 3.8-5.5 3.8-3.3 0-6-2.7-6-6s2.7-6 6-6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.9 3.3 14.7 2.4 12 2.4 6.9 2.4 2.7 6.6 2.7 11.7S6.9 21 12 21c5.2 0 8.6-3.6 8.6-8.7 0-.6-.1-1-.2-1.4H12z"
      />
    </svg>
  )
}

function MicrosoftIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" aria-hidden>
      <path fill="#F25022" d="M3 3h8.5v8.5H3z" />
      <path fill="#7FBA00" d="M12.5 3H21v8.5h-8.5z" />
      <path fill="#00A4EF" d="M3 12.5h8.5V21H3z" />
      <path fill="#FFB900" d="M12.5 12.5H21V21h-8.5z" />
    </svg>
  )
}
