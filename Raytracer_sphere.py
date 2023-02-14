import numpy as np
import tkinter as tk
import colorama as col
import sys

WIDTH = 300
HEIGHT = 200
RATIO = WIDTH / HEIGHT
SCREEN = (-1,1/RATIO,1,-1/RATIO)     #Koordinater för skärmens hörn
OBSERVER = np.array([0, 0, -3])         #Position för observeraren, z kan ändras
AMBIENT = 0.06


"""
Skapa scenen: objekt definieras (plan och klot), ljusets träffpunkt på klotet, hitta ljuskällan (alltid SCALE*radie bort)
skärm: närmaste objekt från kameran till en punkt på SCREEN (find_closest_object(vektor från OBSERVER till SCREEN, punkt OBSERVER))
       blockeras ljuspunkten av andra objekt i scenen (bara klot, aldrig planet)
       färglägg pixel efter:
       plan, ljuset blockeras av klot: ambient ljus
                ej blockerat: planets färg
       klot, ljuset blokeras av klot: "#000000"
            ej blockerat: beräkna hur långt ifrån ljuset punkten sitter (vinkel) genom skalärprodukt
"""


class Gui():
    """Skapar canvas och definierar event"""
    def __init__(self):
        self.window = tk.Tk()
        self.canvas = tk.Canvas(self.window, width=WIDTH, height=HEIGHT, bg="#000000")
        self.img = tk.PhotoImage(width=WIDTH, height=HEIGHT)

        self.window.bind("<Button-1>", self.callback)                                     #Vid vänsterklick kallas callback
        self.canvas.create_image((WIDTH / 2, HEIGHT / 2), image=self.img, state="normal")
        self.canvas.pack()


    def callback(self, event):
        """Skickar event med x, y koordinater för klicket samt objektet så att self.img finns tillgänglig."""
        mouse_pos(event, self)



class Light:
    """Definierar ljusets position."""
    def __init__(self, x, y, scale):
        self.x_screen = x
        self.y_screen = y
        self.scale = scale                              #Hur många gånger radien som är avståndet från ljuskällan till klotet
        self.coordinate = None


    def update_input(self, x, y):
        """Ändrar ljusets träffpunkt på SCREEN."""
        self.x_screen, self.y_screen = x, y


    def set_position(self):
        """Beräknar ljusets position utifrån koordinater där ljuset träffar SCREEN.
            Returnerar None om inget klot träffas annars en array med koordinater för ljusets position."""
        point_screen = np.array([self.x_screen, self.y_screen, 0])                                  #Screen har alltid z=0
        norm_vec = normalized_vector(point_screen - OBSERVER)
        distance, sph = find_closest_object(norm_vec, OBSERVER, Sphere)                              #Ger avståndet till närmaste klot och klotet som objekt i sph
        if not sph:                                                                                  #Då inget klot träffas definieras ingen koordinat för ljuset
            self.coordinate = None
        else:
            intersection_point = OBSERVER + distance * norm_vec                                           #Bestämmer var på klotet ljuset träffar
            self.coordinate = (intersection_point - sph.center) * sph.radius * self.scale + sph.center



class Sphere:
    """Skapar klot och bestämmer hur punkter på klotet färgas."""
    def __init__(self, center, radius, RGB):
        self.center = center
        self.radius = radius
        self.RGB = RGB


    def get_intersection(self, direction, vector_origin):
        """Vi tar in ett sphere objekt, en normaliserad vektor med ursprung i punkten vektor_origin.
            Funktionen löser cirkelns ekvation i tre dimensioner (||x-C||^2=r^2). Ekvationen blir då ett andragradspolynom
            där lösningen är avståndet från origin till klotets yta.
            Returnerar det minsta avständet till ett klot från en origin i riktningen direction. Om inget klot finns returneras None."""
        b = 2 * np.dot(direction, vector_origin - self.center)
        c = np.linalg.norm(vector_origin - self.center) ** 2 - self.radius ** 2
        delta = b ** 2 - 4 * c                                                  #Avgör antalet lösningar
        if delta > 0:                                                           #Om delta är noll eller mindre går vektorn inte genom klotet
            x1 = (-b + np.sqrt(delta)) / 2
            x2 = (-b - np.sqrt(delta)) / 2
            if x1 > 0 and x2 > 0:
                return min(x1,x2)
        return None


    def get_color(self, intersection_point):
        """Intersection är en array som representerar punkten på klotet som ska färgläggas.
            Om punkten är skuggat av något klot (inklusive sig själv) blir punkten svart,
            annars blir punkten mörkare ju större vinkel från ljuset punkten är (skalärprodukt).
            Returnerar färgen på punkten på klotet enligt "#XXXXXX"."""
        norm_surface = normalized_vector(intersection_point - self.center)
        norm_light_ray = normalized_vector(intersection_point - LIGHT.coordinate)
        min_distance, any_sphere = find_closest_object(norm_light_ray, LIGHT.coordinate, Sphere)
        if not any_sphere or round(min_distance, 4) >= round(np.linalg.norm(intersection_point - LIGHT.coordinate), 4):  #Om ingen sfär, eller om närmaste punkten som skär sfären är punkten vi är på, färgas klotet med sin egen färg
            b = (np.dot(norm_surface, -norm_light_ray))                             #Avgör hur mycket punkten är vinklad bort från ljuspunkten
            if b < 0:
                b = 0
            R, G, B = map(lambda x: x * b, self.RGB)                               #Mappar elementen i RGB till variabler efter att ha skalats med b
            return get_RGB([R, G, B], False)
        else: return "#000000"



class Plane:
    """Skapar plan och bestämmer hur punkter på planen färgas."""
    def __init__(self, fixed_axis, fixed_coordinate, RGB):
        self.fixed_axis = fixed_axis                                        #Bestämmer vilken axel som är fixed x:0, y:1 och z:2
        self.fixed_coordinate = fixed_coordinate                            #Bestämmer vilken koordinat som är fixed
        self.base_color = get_RGB(RGB, False)
        self.ambient = get_RGB(RGB, True)                                 #Ändrar ljusintensiteten eftersom ambient=True


    def get_intersection(self, norm_vector, vector_origin):
        """Tar in två array norm_vector, normaliserad vektor, och vector_origin, dess ursprung.
            Vi studerar kordinaterna för den fixerade axeln på planet och kan då bestämma hur mycket
            norm_vector behöver skalas för att nå planet.
            Returnerar avståndet till planet om vektorn kan träffa det. Annars returneras None."""
        if norm_vector[self.fixed_axis] == 0:                                                           #Om koordinaten för den fixerade axen är noll kommer den alltid att vara noll och därför aldrig träffa planet
            return None
        distance = (self.fixed_coordinate - vector_origin[self.fixed_axis]) / norm_vector[self.fixed_axis]     #Beräknar avståndet till planet genom att uttnyttja att en koordinat i planet är fast
        if distance < 0:                                                                                #Negativ riktning är bakom SCREEN och ses alltså aldrig av OBSERVER
            return None
        return distance


    def get_color(self, intersection_point):
        """Ta in array intersection som är en punkt på planet self.
            Samtliga klot i scenen loopas igenom och om vektorn från
            intersection till light går igenom ett klot kallas punkten skuggad, annars inte.
            Returnerar färgen på en punkt på planet enligt "#XXXXXX"."""
        norm_light_ray = normalized_vector(intersection_point - LIGHT.coordinate)
        distance_intersection = np.linalg.norm(intersection_point - LIGHT.coordinate)                 #Avståndet från ljuset till punkten som studeras
        distance, sph = find_closest_object(norm_light_ray, LIGHT.coordinate, Sphere)           #Kortaste avståndet mellan ljuset och någon sfär med vektor från ljus till punkt som studeras
        if not sph:                                                                             #Träffas inga sfärer är punkten ej skuggad
            return self.base_color
        elif distance <= distance_intersection:                                                 #Då planet träffas efter klotet är det skuggat
            return self.ambient
        else:
            return self.base_color                                                              #Om planet träffas innan klotet träffas så är det inte skuggat (ljuspunkten är "bakom" planet)



def find_closest_object(norm_vector, vector_origin, pre_def_obj=type(None)):
    """Tar in två arrays där norm_vector är en normaliserad vector och vector_origin är vektornsursprung.
        pre_def_obj är de objekt som ska loopas igenom. Om inget specificeras loopas alla objekt igenom.
        Loopar igenom objekten i scenen och kallar på objektetsmetod för att bestämma om norm_vector träffar objektet och i så fall hur långt bort.
        Det kortaste avståndet till ett objekt sparas tillsammans med objektet.
        Returnerar det närmaste objektet och avståndet till det."""
    min_distance = ""                                              #Skapat så att det första objektet som träffas väljs oavsett avstånd
    for object in OBJECTS:
        if not isinstance(object, pre_def_obj) and not pre_def_obj is type(None):      #Logik så att antingen alla objekt loopas igenom eller bara ett objekt (pre_def_obj)
            continue
        distance = object.get_intersection(norm_vector, vector_origin)
        if distance != None and (isinstance(min_distance, str) or distance < min_distance):    #Väljer kortaste avståndet till objekt
            min_distance = distance
            closest_object = object
    if min_distance == "":                                  #Inga korsningar i scenen
        return None, None
    else:
        return min_distance, closest_object


def display(window):
    """Tar in tk objektet window.
        Loopar igenom punkter på SCREEN med jämnt avstånd och samlar information
        om det närmaste objektet och färgen på den punkten som träffas. Ändrar färg på pixlarna i window."""
    for i, y in enumerate(np.linspace(SCREEN[1], SCREEN[3], HEIGHT)):
        progress_bar(i + 1, HEIGHT)
        for j, x in enumerate(np.linspace(SCREEN[0], SCREEN[2], WIDTH)):        #Går igenom skärmen med ett konstant avstånd mellan punkterna
            point = np.array([x, y, 0])
            norm_vec = normalized_vector(point - OBSERVER)                      #Skapar vektor av längd 1 från OBSERVER till punkten på SCREEN
            distance, object = find_closest_object(norm_vec, OBSERVER)          #Hämtar närmaste objekt och avståndet dit
            if not object:                                                      #Ingen pixel färgas om inget objekt hittas
                continue
            intersection_point = OBSERVER + distance * norm_vec
            col = object.get_color(intersection_point)                                    #Hittar färgen för punkten på objektet
            window.img.put(col, (j, i))                                          #Använder j och i då detta motsvarar koordinatsystemet i canvas


def normalized_vector(vector):
    """Returnerar en normaliserad vektor"""
    return vector / np.linalg.norm(vector)


def get_RGB(RGB, ambient):
    """Tar in en lista med värden för R, G och B samt en boulien som säger om AMBIENT ska användas eller ej.
    Returnerar ambient light eller objektets egna färg på "#xxxxxx" format."""
    if ambient:
        R, G, B = map(lambda x: int(x * AMBIENT), RGB)                           #Unpackar listan RGB och multiplicerar varje element med AMBIENT om ambient är true
    else: R, G, B = map(int, RGB)                                                #Om det inte är ambient ljus mappas elementen direkt utan att ändras
    return f'#{R:02x}{G:02x}{B:02x}'                                             #Konverterar decimal till hexa där 2 tecken alltid används


def mouse_pos(event, window):
    """Tar in objekten event och window.
    Beräknar x och y på SCREEN vid ett klick, ändrar ljusets position och
    startar upp display om användaren klickat på klotet."""
    x = 2 * (event.x - WIDTH / 2) / WIDTH
    y = 2 * (HEIGHT / 2 - event.y) / (HEIGHT * RATIO)                   #Sparar koordinaterna för klicket som koordinater på SCREEN
    LIGHT.update_input(x, y)
    LIGHT.set_position()                                                #Ändrar ljusets position i scenen
    sys.stdout.write("\033[K")                                          #Rensar printsatser från terminalen. "[F" istället för K om du fill gå upp en rad
    print(col.Fore.RESET, end = "\r")
    if isinstance(LIGHT.coordinate, type(None)):                        #Om inget klot träffas av ljuset avslutas funktionen och ingen förändring sker
        print("Tryck på klotet.", end = "\r")
        return None
    display(window)

def progress_bar(progress, total):
    """Printar progress bar i terminalen."""
    percent = int(50 * progress / total)
    bar = "█" * percent + "-" * (50 - percent)
    print(col.Fore.WHITE + f"\r|{bar}| {2*percent:.0f}%", end="\r")
    if progress == total:
        print(col.Fore.GREEN + f"\r|{bar}| {2*percent:.0f}%", end="\r")

def main():
    """Startar programmet och ser till att startpunkt för ljuset träffar något klot."""
    screen = Gui()
    LIGHT.set_position()
    if isinstance(LIGHT.coordinate, type(None)):
        exit("Ursprungsinställningar för ljuset träffar inget klot i scenen.")
    display(screen)
    print(col.Fore.RESET, end = "\r")
    tk.mainloop()


"""Definierar objekten i scenen."""
OBJECTS = [Sphere(np.array([1, 0, 3]), 0.8, [255, 255, 255]),
           Sphere(np.array([0.6, 0.5, 0.2]), 0.1, [0, 130, 255]),
           Plane(1, -0.8, [130, 130, 130]),
           Plane(1, 2, [130, 130, 130]),
           Plane(0, -2, [0, 200, 22]),
           Plane(0, 2, [0, 200, 22]),
           Plane(2, 10, [240, 30, 24])
           ]

LIGHT = Light(0.3, 0.2, 1000)


if __name__ == "__main__":
    main()