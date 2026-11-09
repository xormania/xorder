<?php

declare(strict_types=1);

// The native engine owns analysis; this worker adds compiled Symfony wiring.
use ByteKitsune\MagoSymfonyWiring\SymfonyWiringExtension;
use Mago\Sdk\Analyzer\AfterAnalysisContext;
use Mago\Sdk\Analyzer\AfterAnalysisHook;
use Mago\Sdk\Analyzer\Metadata\MemberIdentifier;
use Mago\Sdk\Analyzer\Plugin;
use Mago\Sdk\Analyzer\PluginDefinition;
use Mago\Sdk\Analyzer\PluginRegistry;
use Mago\Sdk\Extension;
use Mago\Sdk\Worker;

$root = dirname(__DIR__);
require $root . '/vendor/autoload.php';
$extensions = [];
$graph = getenv('XORDER_MAGO_GRAPH');
if ($graph !== false) {
    $observer = new class($graph) implements Plugin, AfterAnalysisHook {
        public function __construct(private readonly string $path) {}

        public function getDefinition(): PluginDefinition
        {
            return new PluginDefinition('xorder/symfony-observer', 'Symfony graph observation', 'Native final graph references.');
        }

        public function register(PluginRegistry $registry): void
        {
            $registry->registerAfterAnalysisHook($this);
        }

        public function afterAnalysis(AfterAnalysisContext $context): void
        {
            $owners = json_decode(getenv('XORDER_MAGO_SYMBOLS') ?: '["App\\\\Service\\\\Greeting"]', true, flags: JSON_THROW_ON_ERROR);
            if (!is_array($owners) || $owners === [] || count($owners) > 8) {
                throw new RuntimeException('Expected one to eight selected class names.');
            }
            $symbols = [];
            foreach ($owners as $owner) {
                $references = [];
                foreach ($context->analysis->references->getReferencesFrom(new MemberIdentifier($owner, '__construct')) as $edge) {
                    $references[] = ['source' => $edge->source, 'target' => $edge->target, 'kind' => $edge->kind->name];
                }
                $symbols[$owner] = $references;
            }
            file_put_contents($this->path, json_encode([
                'observer' => 'xorder/symfony-observer',
                'wiring_enabled' => getenv('XORDER_MAGO_WIRING') !== '0',
                'symbols' => $symbols,
            ], JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . "\n");
        }
    };
    $extensions[] = new Extension('xorder/observer', 'Native graph observer', '1.0.0', analyzerPlugins: [$observer]);
}
if (getenv('XORDER_MAGO_WIRING') !== '0') {
    $extensions[] = SymfonyWiringExtension::fromContainerReference($root, '.mago/container-reference.dev.json');
}
(new Worker(...$extensions))->run();
