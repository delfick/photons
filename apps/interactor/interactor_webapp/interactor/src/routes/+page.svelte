<script>
	import { io } from 'socket.io-client';
	import { Commands } from '$lib/commands';

	const socketio = io({ path: '/webapp' });
	const commands = new Commands(socketio);

	$: connecting = commands.connecting;
	$: devices = commands.devices;
</script>

<h1>Interactor</h1>

{#if $connecting}
	<p>Connecting...</p>
{:else}
	<ul>
		{#each $devices as device}
			<li>{device.serial}</li>
		{/each}
	</ul>
{/if}
