import { Socket } from 'socket.io-client';
import { ulid } from "ulidx";
import { writable, type Writable } from 'svelte/store';

export class Device {
    constructor(public serial: string) {
    }
}

type MM = {
    [key: string]: unknown
}

type WaitingMap = {
    [key: string]: ((body: MM) => void) | null
};

export class Commands {
    socket: Socket;
    waiting: WaitingMap;
    devices: Writable<Array<Device>>
    connecting: Writable<boolean>

    constructor(socket: Socket) {
        this.socket = socket
        this.devices = writable([])
        this.connecting = writable(true)
        this.waiting = {};

        socket.on('connect', this.connect)
        socket.on('disconnect', this.disconnect)
        socket.on('progress', this.reply);
        socket.on('reply', this.reply);
        socket.on('error', this.reply);
    }

    connect = async (): Promise<void> => {
        const serials = await this.refresh_serials();
        this.connecting.set(false)
        this.devices.set(serials.map(serial => new Device(serial)))
    }

    disconnect = async (): Promise<void> => {
        this.connecting.set(true)
    }

    reply = (body: MM): void => {
        const message_id = body.message_id
        if (typeof message_id == "string") {
            const handle = this.waiting[message_id]
            if (handle) {
                handle(body)
            }
        }
    }

    send<T_Ret>(path: string, options: MM, handler: (data: MM) => T_Ret): Promise<T_Ret> {
        const socket = this.socket;
        if (!socket) {
            return Promise.reject("No active socket")
        }
        return new Promise(resolve => {
            const handle = (data: MM): void => {
                resolve(handler(data))
            };
            const command = { path: path, message_id: ulid(), ...options };
            this.waiting[command.message_id] = handle
            socket.emit('command', command)
        })
    }

    refresh_serials(): Promise<Array<string>> {
        return new Promise(resolve => {
            this.send("/v2/discover/serials", {}, (data: MM) => {
                if (data.reply instanceof Object && "error" in data.reply) {
                    throw new Error(String(data.reply.error))
                }
                if (!Array.isArray(data.reply)) {
                    throw new Error("Reply wasn't an array")
                }
                resolve(data.reply);
            })
        });
    }
}

