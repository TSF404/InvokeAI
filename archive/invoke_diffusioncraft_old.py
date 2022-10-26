#!/usr/bin/env python3
# Copyright (c) 2022 Lincoln D. Stein (https://github.com/lstein)

import os
import re
import sys
import shlex
import copy
import warnings
import random
import time
import traceback
sys.path.append('.')    # corrects a weird problem on Macs
from ldm.invoke.readline import get_completer
from ldm.invoke.args import Args, metadata_dumps, metadata_from_png, dream_cmd_from_png
from ldm.invoke.pngwriter import PngWriter, retrieve_metadata, write_metadata
from ldm.invoke.image_util import make_grid
from ldm.invoke.log import write_log
from omegaconf import OmegaConf
from backend.invoke_ai_web_server import InvokeAIWebServer



PROMPT = 'hyperrealistic dslr film still of early cuyler squidbillies, cephalopod, stunning 8 k octane comprehensive 3 d render, inspired by istvan sandorfi & greg rutkowski & unreal engine, perfect symmetry, dim volumetric cinematic lighting, extremely hyperdetailed, extremely lifelike attributes & texture, intricate, masterpiece, artstation, stunning'
PROMPT = 'biopunk portrait of curly orange hair man from borderlands 3, au naturel, hyper detailed, digital art, trending in artstation, cinematic lighting, studio quality, smooth render, unreal engine 5 rendered, octane rendered, art style by klimt and nixeu and ian sprigger and wlop and krenz cushart. '
PROMPT = 'beautiful hyperrealistic cottage, highly detailed, digital painting, trending artstation, concept art, illustration, cinematic lighting, vibrant colors, photorealism, epic, octane render'
PROMPT = 'scifi futuristic organic concept car on a studio stage, shiny glossy reflections, product render'
PROMPT = 'colourful watercolor of astronaut in space surrounded by planets and stars'
PROMPT = 'crochet bunny with a scarf'
PROMPT = 'photograph of eco-friendly city streets, urban, octane render'

PROMPT = "goddess princess face close-up portrait ram skull abstract 3d composition. jellyfish phoenix head, nautilus, orchid, skull, betta fish, bioluminiscent creatures, intricate artwork by Tooth Wu and wlop and beeple. octane render, trending on artstation, greg rutkowski very coherent symmetrical artwork. cinematic, hyper realism, high detail, octane render, 8k"
PROMPT = 'cinematic mountainscape highly detailed, epic, with old town by greg rutkowski'

LATEST_IMG = ""


def get_latest_image(dirpath, valid_extensions=('jpg','jpeg','png')):
    """
    Get the latest image file in the given directory
    """

    valid_files = [os.path.join(dirpath, filename) for filename in os.listdir(dirpath)]
    valid_files = [f for f in valid_files if '.' in f and \
        f.rsplit('.',1)[-1] in valid_extensions and os.path.isfile(f)]
    if not valid_files:
        raise ValueError("No valid images in %s" % dirpath)
    return max(valid_files, key=os.path.getmtime)


# Checks for updates in the img2img_input folder, processes them
# and saves them out in img2img_output

def get_next_command():  # command string
    global PROMPT, LATEST_IMG

    INPUT_FOLDER = "outputs/img-samples/img2img_input"
    OUTPUT_FOLDER = "outputs/img-samples/img2img_output"
    
    latestImgDir = str(os.getcwd()) + "/" + INPUT_FOLDER
    latestImgFullPath = get_latest_image(latestImgDir, ".png")
    latestImgFileName = os.path.basename(latestImgFullPath)

    # Wait for an updated image (so its not reprocessing same frame)
    print("Comparing - " + latestImgFileName + " " + LATEST_IMG)
    if LATEST_IMG == latestImgFileName:
        time.sleep(0.1)
        return ""

    LATEST_IMG = latestImgFileName

    print("latest filename --- " + INPUT_FOLDER + "/" + latestImgFileName)
    print("output --- " + OUTPUT_FOLDER)


    DENOISING_STRENGTH = 0.54  #str(random.uniform(0.3,0.4))
    SAMPLES = 40
    command = PROMPT + " -I " + INPUT_FOLDER + "/" + latestImgFileName+" -o "+OUTPUT_FOLDER+" -s "+str(SAMPLES)+" -W512 -H512 --fit --strength " + str(DENOISING_STRENGTH)

    return command

    '''
    if infile is None:
        command = input('invoke> ')
    else:
        command = infile.readline()
        if not command:
            raise EOFError
        else:
            command = command.strip()
        if len(command)>0:
            print(f'#{command}')
    return command
    '''


def prepare_image_metadata(
        opt,
        prefix,
        seed,
        operation='generate',
        prior_variations=[],
        postprocessed=False,
        first_seed=None):
    if postprocessed and opt.save_original:
        filename = choose_postprocess_name(opt,prefix,seed)
    else:
        filename = f'{prefix}_{seed}_{commandID}.png'  # <------- FILENAME

    if opt.variation_amount > 0:
        first_seed             = first_seed or seed
        this_variation         = [[seed, opt.variation_amount]]
        opt.with_variations    = prior_variations + this_variation
        formatted_dream_prompt = opt.dream_prompt_str(seed=first_seed)
    elif len(prior_variations) > 0:
        formatted_dream_prompt = opt.dream_prompt_str(seed=first_seed)
    elif operation == 'postprocess':
        formatted_dream_prompt = '!fix '+opt.dream_prompt_str(seed=seed)
    else:
        formatted_dream_prompt = opt.dream_prompt_str(seed=seed)
    return filename,formatted_dream_prompt







commandID = 0

def main():
    """Initialize command-line parsers and the diffusion model"""
    opt  = Args()
    args = opt.parse_args()
    if not args:
        sys.exit(-1)

    if args.laion400m:
        print('--laion400m flag has been deprecated. Please use --model laion400m instead.')
        sys.exit(-1)
    if args.weights:
        print('--weights argument has been deprecated. Please edit ./configs/models.yaml, and select the weights using --model instead.')
        sys.exit(-1)

    print('* Initializing, be patient...\n')
    from ldm.generate import Generate

    # these two lines prevent a horrible warning message from appearing
    # when the frozen CLIP tokenizer is imported
    import transformers
    transformers.logging.set_verbosity_error()

    # Loading Face Restoration and ESRGAN Modules
    try:
        gfpgan, codeformer, esrgan = None, None, None
        if opt.restore or opt.esrgan:
            from ldm.invoke.restoration import Restoration
            restoration = Restoration()
            if opt.restore:
                gfpgan, codeformer = restoration.load_face_restore_models(opt.gfpgan_dir, opt.gfpgan_model_path)
            else:
                print('>> Face restoration disabled')
            if opt.esrgan:
                esrgan = restoration.load_esrgan(opt.esrgan_bg_tile)
            else:
                print('>> Upscaling disabled')
        else:
            print('>> Face restoration and upscaling disabled')
    except (ModuleNotFoundError, ImportError):
        print(traceback.format_exc(), file=sys.stderr)
        print('>> You may need to install the ESRGAN and/or GFPGAN modules')

    # creating a simple text2image object with a handful of
    # defaults passed on the command line.
    # additional parameters will be added (or overriden) during
    # the user input loop
    try:
        gen = Generate(
            conf           = opt.conf,
            model          = opt.model,
            sampler_name   = opt.sampler_name,
            embedding_path = opt.embedding_path,
            full_precision = opt.full_precision,
            precision      = opt.precision,
            gfpgan=gfpgan,
            codeformer=codeformer,
            esrgan=esrgan,
            free_gpu_mem=opt.free_gpu_mem,
            )
    except (FileNotFoundError, IOError, KeyError) as e:
        print(f'{e}. Aborting.')
        sys.exit(-1)

    # make sure the output directory exists
    if not os.path.exists(opt.outdir):
        os.makedirs(opt.outdir)

    # load the infile as a list of lines
    infile = None
    if opt.infile:
        try:
            if os.path.isfile(opt.infile):
                infile = open(opt.infile, 'r', encoding='utf-8')
            elif opt.infile == '-':  # stdin
                infile = sys.stdin
            else:
                raise FileNotFoundError(f'{opt.infile} not found.')
        except (FileNotFoundError, IOError) as e:
            print(f'{e}. Aborting.')
            sys.exit(-1)

    if opt.seamless:
        print(">> changed to seamless tiling mode")

    # preload the model
    gen.load_model()

    # web server loops forever
    if opt.web or opt.gui:
        invoke_ai_web_server_loop(gen, gfpgan, codeformer, esrgan)
        sys.exit(0)

    if not infile:
        print(
            "\n* Initialization done! Awaiting your command (-h for help, 'q' to quit)"
        )

    main_loop(gen, opt, infile)



# TODO: main_loop() has gotten busy. Needs to be refactored.
def main_loop(gen, opt, infile):
    global commandID

    """prompt/read/execute loop"""
    done = False
    path_filter = re.compile(r'[<>:"/\\|?*]')
    last_results = list()
    model_config = OmegaConf.load(opt.conf)[opt.model]

    # The readline completer reads history from the .dream_history file located in the
    # output directory specified at the time of script launch. We do not currently support
    # changing the history file midstream when the output directory is changed.
    completer   = get_completer(opt)
    output_cntr = completer.get_current_history_length()+1

    # os.pathconf is not available on Windows
    if hasattr(os, 'pathconf'):
        path_max = os.pathconf(opt.outdir, 'PC_PATH_MAX')
        name_max = os.pathconf(opt.outdir, 'PC_NAME_MAX')
    else:
        path_max = 260
        name_max = 255



    while not done:
        commandID += 1
        
        operation = 'generate'   # default operation, alternative is 'postprocess'

        if completer:
            completer.set_default_dir(opt.outdir)
            
        try:
            command = get_next_command()
            if command == "":
                print("Empty command.. skipping")
                continue
        except EOFError:
            done = True
            continue
        print("COMMAND GIVEN: " + str(command))
        # skip empty lines
        if not command.strip():
            continue

        if command.startswith(('#', '//')):
            continue

        if len(command.strip()) == 1 and command.startswith('q'):
            done = True
            break

        if command.startswith('!'):
            subcommand = command[1:]

            if subcommand.startswith('dream'):   # in case a stored prompt still contains the !dream command
                command = command.replace('!dream ','',1)

            elif subcommand.startswith('fix'):
                command = command.replace('!fix ','',1)
                operation = 'postprocess'

            elif subcommand.startswith('fetch'):
                file_path = command.replace('!fetch ','',1)
                retrieve_dream_command(opt,file_path,completer)
                continue

            elif subcommand.startswith('history'):
                completer.show_history()
                continue

            elif subcommand.startswith('search'):
                search_str = command.replace('!search ','',1)
                completer.show_history(search_str)
                continue

            elif subcommand.startswith('clear'):
                completer.clear_history()
                continue

            elif re.match('^(\d+)',subcommand):
                command_no = re.match('^(\d+)',subcommand).groups()[0]
                command    = completer.get_line(int(command_no))
                completer.set_line(command)
                continue
                
            else:  # not a recognized subcommand, so give the --help text
                command = '-h'

        if opt.parse_cmd(command) is None:
            continue

        if opt.init_img:
            try:
                if not opt.prompt:
                    oldargs    = metadata_from_png(opt.init_img)
                    opt.prompt = oldargs.prompt
                    print(f'>> Retrieved old prompt "{opt.prompt}" from {opt.init_img}')
            except (OSError, AttributeError, KeyError):
                pass

        if len(opt.prompt) == 0:
            print('\nTry again with a prompt!')
            continue

        # width and height are set by model if not specified
        if not opt.width:
            opt.width = model_config.width
        if not opt.height:
            opt.height = model_config.height

        # retrieve previous value of init image if requested
        if opt.init_img is not None and re.match('^-\\d+$', opt.init_img):
            try:
                opt.init_img = last_results[int(opt.init_img)][0]
                print(f'>> Reusing previous image {opt.init_img}')
            except IndexError:
                print(
                    f'>> No previous initial image at position {opt.init_img} found')
                opt.init_img = None
                continue

        # try to relativize pathnames
        for attr in ('init_img','init_mask','init_color','embedding_path'):
            if getattr(opt,attr) and not os.path.exists(getattr(opt,attr)):
                basename = getattr(opt,attr)
                path     = os.path.join(opt.outdir,basename)
                setattr(opt,attr,path)

        # retrieve previous value of seed if requested
        if opt.seed is not None and opt.seed < 0:   
            try:
                opt.seed = last_results[opt.seed][1]
                print(f'>> Reusing previous seed {opt.seed}')
            except IndexError:
                print(f'>> No previous seed at position {opt.seed} found')
                opt.seed = None
                continue

        if opt.strength is None:
            opt.strength = 0.75 if opt.out_direction is None else 0.83

        if opt.with_variations is not None:
            opt.with_variations = split_variations(opt.with_variations)

        if opt.prompt_as_dir and operation == 'generate':
            # sanitize the prompt to a valid folder name
            subdir = path_filter.sub('_', opt.prompt)[:name_max].rstrip(' .')

            # truncate path to maximum allowed length
            # 39 is the length of '######.##########.##########-##.png', plus two separators and a NUL
            subdir = subdir[:(path_max - 39 - len(os.path.abspath(opt.outdir)))]
            current_outdir = os.path.join(opt.outdir, subdir)

            print('Writing files to directory: "' + current_outdir + '"')

            # make sure the output directory exists
            if not os.path.exists(current_outdir):
                os.makedirs(current_outdir)
        else:
            if not os.path.exists(opt.outdir):
                os.makedirs(opt.outdir)
            current_outdir = opt.outdir

        # write out the history at this point
        if operation == 'postprocess':
            completer.add_history(f'!fix {command}')
        else:
            completer.add_history(command)

        # Here is where the images are actually generated!
        last_results = []
        try:
            file_writer      = PngWriter(current_outdir)
            results          = []  # list of filename, prompt pairs
            grid_images      = dict()  # seed -> Image, only used if `opt.grid`
            prior_variations = opt.with_variations or []
            prefix = file_writer.unique_prefix()
            step_callback = make_step_callback(gen, opt, prefix) if opt.save_intermediates > 0 else None

            def image_writer(image, seed, upscaled=False, first_seed=None, use_prefix=None):
                # note the seed is the seed of the current image
                # the first_seed is the original seed that noise is added to
                # when the -v switch is used to generate variations
                nonlocal prior_variations
                nonlocal prefix
                if use_prefix is not None:
                    prefix = use_prefix

                path = None
                if opt.grid:
                    grid_images[seed] = image
                else:
                    postprocessed = upscaled if upscaled else operation=='postprocess'
                    filename, formatted_dream_prompt = prepare_image_metadata(
                        opt,
                        prefix,
                        seed,
                        operation,
                        prior_variations,
                        postprocessed,
                        first_seed
                    )
                    path = file_writer.save_image_and_prompt_to_png(
                        image           = image,
                        dream_prompt    = formatted_dream_prompt,
                        metadata        = metadata_dumps(
                            opt,
                            seeds      = [seed if opt.variation_amount==0 and len(prior_variations)==0 else first_seed],
                            model_hash = gen.model_hash,
                        ),
                        name      = filename,
                    )

                    # update rfc metadata
                    if operation == 'postprocess':
                        tool = re.match('postprocess:(\w+)',opt.last_operation).groups()[0]
                        add_postprocessing_to_metadata(
                            opt,
                            opt.prompt,
                            filename,
                            tool,
                            formatted_dream_prompt,
                        )                           
                        
                    if (not postprocessed) or opt.save_original:
                        # only append to results if we didn't overwrite an earlier output
                        results.append([path, formatted_dream_prompt])

                # so that the seed autocompletes (on linux|mac when -S or --seed specified
                if completer:
                    completer.add_seed(seed)
                    completer.add_seed(first_seed)
                last_results.append([path, seed])

            if operation == 'generate':
                catch_ctrl_c = infile is None # if running interactively, we catch keyboard interrupts
                opt.last_operation='generate'
                gen.prompt2image(
                    image_callback=image_writer,
                    step_callback=step_callback,
                    catch_interrupts=catch_ctrl_c,
                    **vars(opt)
                )
            elif operation == 'postprocess':
                print(f'>> fixing {opt.prompt}')
                opt.last_operation = do_postprocess(gen,opt,image_writer)

            if opt.grid and len(grid_images) > 0:
                grid_img   = make_grid(list(grid_images.values()))
                grid_seeds = list(grid_images.keys())
                first_seed = last_results[0][1]
                filename   = f'{prefix}_{first_seed}_{commandID}.png'
                formatted_dream_prompt  = opt.dream_prompt_str(seed=first_seed,grid=True,iterations=len(grid_images))
                formatted_dream_prompt += f' # {grid_seeds}'
                metadata = metadata_dumps(
                    opt,
                    seeds      = grid_seeds,
                    model_hash = gen.model_hash
                    )
                path = file_writer.save_image_and_prompt_to_png(
                    image        = grid_img,
                    dream_prompt = formatted_dream_prompt,
                    metadata     = metadata,
                    name         = filename
                )
                results = [[path, formatted_dream_prompt]]

        except AssertionError as e:
            print(e)
            continue

        except OSError as e:
            print(e)
            continue

        print('Outputs:')
        log_path = os.path.join(current_outdir, 'invoke_log')
        output_cntr = write_log(results, log_path ,('txt', 'md'), output_cntr)
        print()

    print('goodbye!')

def do_postprocess (gen, opt, callback):
    file_path = opt.prompt     # treat the prompt as the file pathname
    if os.path.dirname(file_path) == '': #basename given
        file_path = os.path.join(opt.outdir,file_path)

    tool=None
    if opt.gfpgan_strength > 0:
        tool = opt.facetool
    elif opt.embiggen:
        tool = 'embiggen'
    elif opt.upscale:
        tool = 'upscale'
    elif opt.out_direction:
        tool = 'outpaint'
    elif opt.outcrop:
        tool = 'outcrop'
    opt.save_original  = True # do not overwrite old image!
    opt.last_operation = f'postprocess:{tool}'
    try:
        gen.apply_postprocessor(
            image_path      = file_path,
            tool            = tool,
            gfpgan_strength = opt.gfpgan_strength,
            codeformer_fidelity = opt.codeformer_fidelity,
            save_original       = opt.save_original,
            upscale             = opt.upscale,
            out_direction       = opt.out_direction,
            outcrop             = opt.outcrop,
            callback            = callback,
            opt                 = opt,
        )
    except OSError:
        print(traceback.format_exc(), file=sys.stderr)
        print(f'** {file_path}: file could not be read')
        return
    except (KeyError, AttributeError):
        print(traceback.format_exc(), file=sys.stderr)
        return
    return opt.last_operation

def add_postprocessing_to_metadata(opt,original_file,new_file,tool,command):
    original_file = original_file if os.path.exists(original_file) else os.path.join(opt.outdir,original_file)
    new_file       = new_file     if os.path.exists(new_file)      else os.path.join(opt.outdir,new_file)
    meta = retrieve_metadata(original_file)['sd-metadata']
    img_data = meta['image']
    pp = img_data.get('postprocessing',[]) or []
    pp.append(
        {
            'tool':tool,
            'dream_command':command,
        }
    )
    meta['image']['postprocessing'] = pp
    write_metadata(new_file,meta)
    
def choose_postprocess_name(opt,prefix,seed) -> str:
    match      = re.search('postprocess:(\w+)',opt.last_operation)
    if match:
        modifier = match.group(1)   # will look like "gfpgan", "upscale", "outpaint" or "embiggen"
    else:
        modifier = 'postprocessed'

    counter   = 0
    filename  = None
    available = False
    while not available:
        if counter == 0:
            filename = f'{prefix}_{seed}_{modifier}_{commandID}.png'
        else:
            filename = f'{prefix}_{seed}_{modifier}_{commandID}-{counter:02d}.png'
        available = not os.path.exists(os.path.join(opt.outdir,filename))
        counter += 1
    return filename





def invoke_ai_web_server_loop(gen, gfpgan, codeformer, esrgan):
    print('\n* --web was specified, starting web server...')
    # Change working directory to the stable-diffusion directory
    os.chdir(
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    )
    
    invoke_ai_web_server = InvokeAIWebServer(generate=gen, gfpgan=gfpgan, codeformer=codeformer, esrgan=esrgan)

    try:
        invoke_ai_web_server.run()
    except KeyboardInterrupt:
        pass
    

def split_variations(variations_string) -> list:
    # shotgun parsing, woo
    parts = []
    broken = False  # python doesn't have labeled loops...
    for part in variations_string.split(','):
        seed_and_weight = part.split(':')
        if len(seed_and_weight) != 2:
            print(f'** Could not parse with_variation part "{part}"')
            broken = True
            break
        try:
            seed   = int(seed_and_weight[0])
            weight = float(seed_and_weight[1])
        except ValueError:
            print(f'** Could not parse with_variation part "{part}"')
            broken = True
            break
        parts.append([seed, weight])
    if broken:
        return None
    elif len(parts) == 0:
        return None
    else:
        return parts

def make_step_callback(gen, opt, prefix):
    destination = os.path.join(opt.outdir,'intermediates',prefix)
    os.makedirs(destination,exist_ok=True)
    print(f'>> Intermediate images will be written into {destination}')
    def callback(img, step):
        if step % opt.save_intermediates == 0 or step == opt.steps-1:
            filename = os.path.join(destination,f'{step:04}.png')
            image = gen.sample_to_image(img)
            image.save(filename,'PNG')
    return callback
    
def retrieve_dream_command(opt,file_path,completer):
    '''
    Given a full or partial path to a previously-generated image file,
    will retrieve and format the dream command used to generate the image,
    and pop it into the readline buffer (linux, Mac), or print out a comment
    for cut-and-paste (windows)
    '''
    dir,basename = os.path.split(file_path)
    if len(dir) == 0:
        path = os.path.join(opt.outdir,basename)
    else:
        path = file_path
    try:
        cmd = dream_cmd_from_png(path)
    except OSError:
        print(f'** {path}: file could not be read')
        return
    except (KeyError, AttributeError):
        print(f'** {path}: file has no metadata')
        return
    completer.set_line(cmd)

if __name__ == '__main__':
    main()
