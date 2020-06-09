from tkinter import *
from tkinter import ttk
from tkinter import filedialog as fd
from PIL import ImageTk, Image
import jnius_config
import os
import multiprocessing as mp

from utils.scrollable_image import ScrollableImage
from utils.level_utils import read_level_from_file, one_hot_to_ascii_level, place_a_mario_token
from utils.level_image_gen import LevelImageGen
from utils.toad_gan_utils import load_trained_pyramid, generate_sample, TOADGAN_obj


MARIO_AI_PATH = os.path.abspath(os.path.join(os.path.curdir, "../Mario-AI-Framework"))
os.environ["MARIO_AI_PATH"] = MARIO_AI_PATH
jnius_config.add_classpath(os.path.join(MARIO_AI_PATH, "src"))
import jnius


class LevelObject:
    def __init__(self, ascii_level, oh_level, image, tokens):
        self.ascii_level = ascii_level
        self.oh_level = oh_level
        self.image = image
        self.tokens = tokens


def TOAD_GUI():
    # Init Window
    root = Tk(className=" TOAD-GUI")

    # Define Variables
    ImgGen = LevelImageGen(os.path.join(os.path.join(os.curdir, "utils"), "sprites"))
    current_level, current_tokens = read_level_from_file(os.path.join(os.curdir, "levels"), "lvl_1-1.txt")

    levelimage = ImageTk.PhotoImage(ImgGen.render(one_hot_to_ascii_level(current_level, current_tokens)))

    level_obj = LevelObject(one_hot_to_ascii_level(current_level, current_tokens),
                            current_level, levelimage, current_tokens)
    toadgan_obj = TOADGAN_obj(None, None, None, None, None, None)

    load_string_gen = StringVar()
    load_string_txt = StringVar()
    error_msg = StringVar()
    use_gen = BooleanVar()
    is_loaded = BooleanVar()

    load_string_gen.set("Click 'Open' to load a Generator or a Level")
    load_string_txt.set(os.path.join(os.curdir, "levels"))
    error_msg.set("No Errors")
    use_gen.set(False)
    is_loaded.set(False)

    # Define Callbacks
    def load_level():
        fname = fd.askopenfilename(title='Load Level', initialdir=os.curdir,
                                   filetypes=[("level .txt files", "*.txt")])
        try:
            if fname[-3:] == "txt":
                load_string_gen.set(fname)
                folder, lname = os.path.split(fname)

                lev, tok = read_level_from_file(folder, lname)

                level_obj.oh_level = lev
                level_obj.ascii_level = one_hot_to_ascii_level(lev, tok)
                m_exists = False
                for line in level_obj.ascii_level:
                    if 'M' in line:
                        m_exists = True
                if not m_exists:
                    level_obj.ascii_level = place_a_mario_token(level_obj.ascii_level)
                level_obj.tokens = tok

                img = ImageTk.PhotoImage(ImgGen.render(level_obj.ascii_level))
                level_obj.image = img

                use_gen.set(False)
                is_loaded.set(True)
            else:
                error_msg.set("Can only load .txt levels.")
        except Exception:
            error_msg.set("Could not load generator/level. Is the filepath correct?")

        return

    def load_generator():
        fname = fd.askdirectory(title='Load Generator Directory', initialdir=os.curdir)

        try:
            load_string_gen.set(fname)
            folder = fname

            loadgan, msg = load_trained_pyramid(folder)
            toadgan_obj.Gs = loadgan.Gs
            toadgan_obj.Zs = loadgan.Zs
            toadgan_obj.reals = loadgan.reals
            toadgan_obj.NoiseAmp = loadgan.NoiseAmp
            toadgan_obj.token_list = loadgan.token_list
            toadgan_obj.num_layers = loadgan.num_layers

            error_msg.set(msg)

            use_gen.set(True)
            is_loaded.set(False)

        except Exception:
            error_msg.set("Could not load generator/level. Is the filepath correct?")

        return

    def save_txt():
        save_name = fd.asksaveasfile(title='Save level', initialdir=os.path.join(os.curdir, "levels"), mode='w',
                                     defaultextension=".txt", filetypes=[("txt files", "*.txt")])
        if save_name is None:
            return  # saving was cancelled
        text2save = ''.join(level_obj.ascii_level)
        save_name.write(text2save)
        save_name.close()
        return

    def generate():
        if toadgan_obj.Gs is None:
            error_msg.set("Generator did not load correctly. Are all necessary files in the folder?")
        else:
            print("Level generated!")
            level = generate_sample(toadgan_obj.Gs, toadgan_obj.Zs, toadgan_obj.reals, toadgan_obj.NoiseAmp,
                                    toadgan_obj.num_layers, toadgan_obj.token_list).cpu()
            level_obj.oh_level = level
            level_obj.ascii_level = one_hot_to_ascii_level(level, toadgan_obj.token_list)
            m_exists = False
            for line in level_obj.ascii_level:
                if 'M' in line:
                    m_exists = True
            if not m_exists:
                level_obj.ascii_level = place_a_mario_token(level_obj.ascii_level)
            level_obj.tokens = toadgan_obj.token_list

            img = ImageTk.PhotoImage(ImgGen.render(level_obj.ascii_level))

            level_obj.image = img

            is_loaded.set(True)
            error_msg.set("Level Generated")
        return

    def play_level():
        # try:
        print("Playing level!")
        MarioGame = jnius.autoclass("engine.core.MarioGame")
        game = MarioGame()
        result = game.playGame(''.join(level_obj.ascii_level), 200)
        # System = jnius.autoclass("java.lang.System")
        # System.exit(0)
        game.window.dispose()
        # except Exception:
        #     error_msg.set("Java Mario Framework crashed. Please check your installation.")
        # print(result.getCompletionPercentage())
        error_msg.set("Level Played. Completion Percentage: %d%%" % int(result.getCompletionPercentage() * 100))
        return

    # Make layout
    settings = ttk.Frame(root, padding=(15, 15, 15, 15), width=1000, height=1000)

    f_label = ttk.Label(settings, text='Path:')
    fpath_label = ttk.Label(settings, textvariable=load_string_gen, width=100)
    load_lev_button = ttk.Button(settings, text='Open Level', command=load_level)
    load_gen_button = ttk.Button(settings, text='Open Generator', command=load_generator)

    gen_button = ttk.Button(settings, text='Generate level', state='disabled', command=generate)
    save_button = ttk.Button(settings, text='Save level', state='disabled', command=save_txt)

    def set_button_state(t1, t2, t3):
        if use_gen.get():
            gen_button.state(['!disabled'])
            save_button.state(['!disabled'])
        else:
            gen_button.state(['disabled'])
            save_button.state(['disabled'])
        return

    use_gen.trace("w", callback=set_button_state)

    play_button = ttk.Button(settings, text='Play level', state='disabled', command=play_level)

    prev_label = ttk.Label(settings, text='Preview:')
    image_label = ScrollableImage(settings, image=levelimage)

    def set_play_state(t1, t2, t3):
        if is_loaded.get():
            play_button.state(['!disabled'])
            image_label.change_image(level_obj.image)
        else:
            play_button.state(['disabled'])
        return

    is_loaded.trace("w", callback=set_play_state)

    error_label = ttk.Label(settings, textvariable=error_msg)

    # Pack layout to grid
    settings.grid(column=0, row=0, sticky=(N, S, E, W))
    f_label.grid(column=0, row=0, columnspan=4, sticky=(S, W), padx=5, pady=5)
    fpath_label.grid(column=0, row=1, columnspan=4, sticky=(N, W), padx=5, pady=5)
    load_lev_button.grid(column=1, row=2, sticky=(N, S, E, W), padx=5, pady=5)
    load_gen_button.grid(column=2, row=2, sticky=(N, S, E, W), padx=5, pady=5)
    gen_button.grid(column=1, row=3, sticky=(N, S, E, W), padx=5, pady=5)
    save_button.grid(column=2, row=3, sticky=(N, S, E, W), padx=5, pady=5)
    prev_label.grid(column=0, row=4, columnspan=4, sticky=(S, W), padx=5, pady=5)
    image_label.grid(column=0, row=5, columnspan=4, sticky=(N, E, W), padx=5, pady=5)
    play_button.grid(column=1, row=6, columnspan=2,  sticky=(N, S, E, W), padx=5, pady=5)
    error_label.grid(column=0, row=10, columnspan=4, sticky=(S, E, W), padx=5, pady=5)

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    settings.columnconfigure(0, weight=1)
    settings.columnconfigure(1, weight=1)
    settings.columnconfigure(2, weight=1)
    settings.columnconfigure(3, weight=1)
    settings.rowconfigure(0, weight=1)
    settings.rowconfigure(1, weight=1)
    settings.rowconfigure(2, weight=1)
    settings.rowconfigure(3, weight=1)
    settings.rowconfigure(4, weight=1)
    settings.rowconfigure(5, weight=1)
    settings.rowconfigure(6, weight=1)
    settings.rowconfigure(10, weight=1)

    # Run Window
    root.mainloop()