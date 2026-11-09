<?php

declare(strict_types=1);

use Symfony\Component\DependencyInjection\Loader\Configurator\ContainerConfigurator;

// Context maps are supported by both the PoC's 0.15 and the 1.0 beta extensions.
return static function (ContainerConfigurator $container): void {
    $container->parameters()
        ->set('mate.php_version', '__PHP_VERSION__')
        ->set('ai_mate_symfony.cache_dir', ['inspection-dev' => '%mate.root_dir%/var/cache/dev'])
        ->set('ai_mate_symfony.profiler_dir', ['inspection-dev' => '%mate.root_dir%/var/cache/dev/profiler'])
        ->set('ai_mate_monolog.log_dir', ['inspection-dev' => '%mate.root_dir%/var/log'])
    ;
};
