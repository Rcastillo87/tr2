<?php

namespace App\Notifications;

use Illuminate\Notifications\Notification;

/**
 * Aviso del sistema en la plataforma (collector, validación, reparación, búsquedas). Solo canal database y sin
 * ShouldQueue: se guarda en el acto, aunque Horizon esté caído.
 */
class SystemAlert extends Notification
{
    public function __construct(
        public readonly string $level,      // info | success | warning | error
        public readonly string $category,   // collector | validation | repair | search
        public readonly string $title,
        public readonly string $body = '',
        public readonly ?string $url = null,
        public readonly ?string $incident = null,
    ) {
    }

    public function via(object $notifiable): array
    {
        return ['database'];
    }

    public function toArray(object $notifiable): array
    {
        return [
            'level'    => $this->level,
            'category' => $this->category,
            'title'    => $this->title,
            'body'     => $this->body,
            'url'      => $this->url,
            'incident' => $this->incident,
        ];
    }
}
