<?php

declare(strict_types=1);

namespace App\Controller;

use App\Service\Greeting;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

final readonly class HomeController
{
    public function __construct(private Greeting $greeting) {}

    #[Route('/', name: 'home')]
    public function __invoke(): Response
    {
        return new Response($this->greeting->message());
    }
}
