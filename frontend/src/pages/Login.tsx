import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  Globe,
  Scale,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

interface LoginForm {
  email: string
  password: string
  full_name?: string
}

type Mode = 'login' | 'register'

const features = [
  'Analyse juridique intelligente',
  'Détection automatique des risques',
  'Suivi des analyses en temps réel',
  'Rapports exportables en un clic',
]

export function LoginPage() {
  const navigate = useNavigate()
  const auth = useAuth()
  const [showPassword, setShowPassword] = useState(false)
  const [mode, setMode] = useState<Mode>('login')
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    defaultValues: {
      email: '',
      password: '',
      full_name: '',
    },
  })

  const onSubmit = async (values: LoginForm) => {
    setFormError(null)
    try {
      if (mode === 'register') {
        await auth.register({
          email: values.email,
          password: values.password,
          full_name: values.full_name?.trim() || undefined,
        })
      } else {
        await auth.login(values.email, values.password)
      }
      navigate('/dashboard')
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : 'Une erreur est survenue',
      )
    }
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
                Intelligence juridique
              </p>
            </div>
          </div>
          <h1 className="mt-16 max-w-md text-4xl font-bold leading-tight">
            Analysez vos contrats avec la précision d’un cabinet, à la vitesse du numérique.
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
              Plateforme juridique intelligente
            </div>
            <h2 className="text-3xl font-bold text-slate-900">
              {mode === 'register' ? 'Créer un compte' : 'Bienvenue !'}
            </h2>
            <p className="mt-2 text-sm text-muted">
              {mode === 'register'
                ? 'Renseignez vos informations pour créer votre espace LegalLink.'
                : 'Connectez-vous pour accéder à vos analyses et consultations.'}
            </p>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
            {formError ? (
              <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-red-50 px-3 py-2.5 text-sm text-danger">
                <AlertCircle className="mt-0.5 size-4 shrink-0" />
                <span>{formError}</span>
              </div>
            ) : null}
            {mode === 'register' ? (
              <Input
                label="Nom complet"
                type="text"
                placeholder="Me. Prénom Nom"
                error={errors.full_name?.message}
                {...register('full_name', {
                  required: 'Nom requis',
                })}
              />
            ) : null}
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
              <label className="mb-1.5 block text-sm font-medium text-slate-700">
                Mot de passe
              </label>
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
              {isSubmitting
                ? mode === 'register'
                  ? 'Création…'
                  : 'Connexion…'
                : mode === 'register'
                  ? 'Créer mon compte'
                  : 'Se connecter'}
            </Button>
          </form>

          <p className="mt-8 text-center text-sm text-muted">
            {mode === 'register' ? (
              <>
                Vous avez déjà un compte ?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('login')
                    setFormError(null)
                  }}
                  className="font-medium text-brand hover:underline"
                >
                  Se connecter
                </button>
              </>
            ) : (
              <>
                Pas encore de compte ?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('register')
                    setFormError(null)
                  }}
                  className="font-medium text-brand hover:underline"
                >
                  Créer un compte
                </button>
              </>
            )}
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
