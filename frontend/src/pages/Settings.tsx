import { LogOut } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { useAuth } from '@/context/AuthContext'

export function SettingsPage() {
  const { user, logout } = useAuth()

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Card padding="lg">
        <CardHeader title="Profil" subtitle="Informations de votre compte" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Nom"
            defaultValue={user?.full_name ?? ''}
            key={user?.full_name}
            readOnly
          />
          <Input
            label="E-mail"
            defaultValue={user?.email ?? ''}
            key={user?.email}
            readOnly
          />
          <div className="sm:col-span-2">
            <Input
              label="Rôle"
              defaultValue={user?.role ?? ''}
              key={user?.role}
              readOnly
            />
          </div>
        </div>
      </Card>

      <Card padding="lg">
        <CardHeader title="Session" subtitle="Gérer votre connexion" />
        <Button
          variant="secondary"
          leftIcon={<LogOut className="size-4" />}
          onClick={logout}
        >
          Se déconnecter
        </Button>
      </Card>
    </div>
  )
}
