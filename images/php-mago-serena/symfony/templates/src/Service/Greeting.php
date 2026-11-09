<?php

declare(strict_types=1);

namespace App\Service;

use Psr\Log\LoggerInterface;

final readonly class Greeting
{
    public function __construct(private LoggerInterface $logger) {}

    public function message(): string
    {
        $this->logger->info('xorder Symfony readiness');

        return 'Symfony Mago development ready';
    }
}
