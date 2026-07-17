import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { currentUser } from '@/data/mock'
import { cn } from '@/lib/cn'

const tabs = [
  'Profil',
  'Sécurité',
  'IA & Modèles',
  'Notifications',
  'Organisation',
  'Intégrations',
  'API',
]

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState('Sécurité')
  const [twoFactor, setTwoFactor] = useState(true)
  const [temperature, setTemperature] = useState(0.3)
  const [notifications, setNotifications] = useState({
    email: true,
    analysisDone: true,
    errors: true,
    weekly: false,
  })

  const { register, handleSubmit } = useForm({
    defaultValues: {
      currentPassword: '',
      newPassword: '',
      model: 'gpt-4o',
      maxTokens: 4096,
    },
  })

  return (
    <div className="space-y-6">
      <Card padding="none">
        <div className="flex gap-1 overflow-x-auto border-b border-border px-2 scrollbar-thin">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={cn(
                'whitespace-nowrap px-4 py-3 text-sm font-medium transition-colors',
                activeTab === tab
                  ? 'border-b-2 border-brand text-brand'
                  : 'text-muted hover:text-slate-800',
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </Card>

      {activeTab === 'Profil' ? (
        <Card padding="lg">
          <CardHeader title="Profil" subtitle="Informations du compte" />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Nom" defaultValue={currentUser.name} readOnly />
            <Input label="E-mail" defaultValue={currentUser.email} readOnly />
            <Input label="Rôle" defaultValue={currentUser.role} readOnly />
          </div>
        </Card>
      ) : null}

      {activeTab === 'Sécurité' ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card padding="lg">
            <CardHeader title="Mot de passe" subtitle="Mettez à jour vos identifiants" />
            <form
              className="space-y-4"
              onSubmit={handleSubmit(() => undefined)}
            >
              <Input
                label="Mot de passe actuel"
                type="password"
                {...register('currentPassword')}
              />
              <Input
                label="Nouveau mot de passe"
                type="password"
                {...register('newPassword')}
              />
              <Button type="submit">Mettre à jour</Button>
            </form>
          </Card>
          <Card padding="lg">
            <CardHeader title="Authentification à deux facteurs" />
            <ToggleRow
              label="Activer la 2FA"
              description="Protection renforcée à la connexion"
              checked={twoFactor}
              onChange={setTwoFactor}
            />
            <div className="mt-6">
              <h4 className="mb-3 text-sm font-semibold">Sessions actives</h4>
              <ul className="space-y-2 text-sm">
                <li className="rounded-lg bg-slate-50 px-3 py-2">
                  Chrome · Windows · Casablanca — session actuelle
                </li>
                <li className="rounded-lg bg-slate-50 px-3 py-2">
                  Safari · iPhone · Dernière activité il y a 2 j
                </li>
              </ul>
            </div>
          </Card>
        </div>
      ) : null}

      {activeTab === 'IA & Modèles' ? (
        <Card padding="lg">
          <CardHeader
            title="Préférences IA"
            subtitle="Paramètres utilisés par le pipeline d’analyse"
          />
          <form className="grid max-w-xl gap-5" onSubmit={handleSubmit(() => undefined)}>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">
                Modèle
              </label>
              <select
                className="h-11 w-full rounded-lg border border-border bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
                {...register('model')}
              >
                <option value="gpt-4o">GPT-4o</option>
                <option value="gpt-4.1">GPT-4.1</option>
                <option value="claude-sonnet">Claude Sonnet</option>
              </select>
            </div>
            <div>
              <div className="mb-1.5 flex justify-between text-sm">
                <span className="font-medium text-slate-700">Temperature</span>
                <span className="text-muted">{temperature.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                className="w-full accent-brand"
              />
            </div>
            <Input
              label="Max tokens"
              type="number"
              {...register('maxTokens', { valueAsNumber: true })}
            />
            <Button type="submit" className="w-fit">
              Enregistrer
            </Button>
          </form>
        </Card>
      ) : null}

      {activeTab === 'Notifications' ? (
        <Card padding="lg">
          <CardHeader title="Notifications" />
          <div className="space-y-1">
            <ToggleRow
              label="E-mail"
              description="Recevoir les alertes par e-mail"
              checked={notifications.email}
              onChange={(v) => setNotifications((n) => ({ ...n, email: v }))}
            />
            <ToggleRow
              label="Analyse terminée"
              description="Notification quand un rapport est prêt"
              checked={notifications.analysisDone}
              onChange={(v) =>
                setNotifications((n) => ({ ...n, analysisDone: v }))
              }
            />
            <ToggleRow
              label="Alertes d’erreur"
              description="Échecs OCR, pipeline ou API"
              checked={notifications.errors}
              onChange={(v) => setNotifications((n) => ({ ...n, errors: v }))}
            />
            <ToggleRow
              label="Résumé hebdomadaire"
              description="Digest chaque lundi matin"
              checked={notifications.weekly}
              onChange={(v) => setNotifications((n) => ({ ...n, weekly: v }))}
            />
          </div>
        </Card>
      ) : null}

      {!['Profil', 'Sécurité', 'IA & Modèles', 'Notifications'].includes(
        activeTab,
      ) ? (
        <Card padding="lg">
          <CardHeader title={activeTab} />
          <p className="text-sm text-muted">
            Section prête pour l’intégration backend (organisation, webhooks,
            clés API).
          </p>
        </Card>
      ) : null}
    </div>
  )
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description: string
  checked: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border py-4 last:border-0">
      <div>
        <p className="text-sm font-medium text-slate-900">{label}</p>
        <p className="text-xs text-muted">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-6 w-11 rounded-full transition-colors',
          checked ? 'bg-brand' : 'bg-slate-300',
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow transition-transform',
            checked && 'translate-x-5',
          )}
        />
      </button>
    </div>
  )
}
