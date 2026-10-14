<?php
// Check the effective Composer policy before an install can select a VCS source.
try {
    if (!preg_match('/Composer(?: version)? (\d+\.\d+\.\d+)(?:\s|$)/', $argv[1] ?? '', $match)
        || version_compare($match[1], '2.10.0', '<')) {
        throw new RuntimeException('Dist-only installs require Composer 2.10 or newer with source fallback disabled');
    }
    if (trim($argv[2] ?? '') !== 'false') {
        throw new RuntimeException('Effective Composer source-fallback must be false; remove the enabling project/global setting');
    }
    $lock = json_decode(file_get_contents('composer.lock'), true, flags: JSON_THROW_ON_ERROR);
    foreach (array_merge($lock['packages'] ?? [], $lock['packages-dev'] ?? []) as $package) {
        if (($package['type'] ?? '') === 'metapackage') { continue; }
        $dist = $package['dist'] ?? [];
        if (!in_array($dist['type'] ?? '', ['zip', 'tar', 'rar', 'xz', 'gzip', 'phar', 'file'], true)
            || !is_string($dist['url'] ?? null) || trim($dist['url']) === '') {
            throw new RuntimeException('No supported dist artifact for '.($package['name'] ?? 'unknown package'));
        }
    }
    // Composer can preserve a previous source installation during an update,
    // even with --prefer-dist. Do not update a partial source tree in place.
    if (is_file('vendor/composer/installed.json')) {
        $installed = json_decode(file_get_contents('vendor/composer/installed.json'), true, flags: JSON_THROW_ON_ERROR);
        foreach ($installed['packages'] ?? [] as $package) {
            if (($package['installation-source'] ?? '') === 'source' && ($package['type'] ?? '') !== 'metapackage') {
                throw new RuntimeException('Incomplete source installation for '.($package['name'] ?? 'unknown package').'; prepare a private dist tree or reuse a complete installation');
            }
        }
    }
} catch (Throwable $error) {
    fwrite(STDERR, 'Dist-only Composer install blocked: '.$error->getMessage()."\n");
    exit(1);
}
